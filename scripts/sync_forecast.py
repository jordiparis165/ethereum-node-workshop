"""Estimate catch-up from confirmed head timestamps, not execution counters."""
from datetime import datetime, timedelta, timezone


def forecast(status, history, deadline):
    now = datetime.fromisoformat(status["observed_at"])
    end = datetime.fromisoformat(deadline)
    result = {"observed_at": status["observed_at"], "deadline": deadline,
              "seconds_until_deadline": max(0, (end - now).total_seconds()),
              "eta_seconds": None, "on_track_estimate": None}
    if status.get("fully_synced"):
        return dict(result, state="verified_synced", eta_seconds=0,
                    on_track_estimate=now <= end)
    migration = status.get("storage_migration") or {}
    if migration.get("phase") not in (None, "activated"):
        state = "storage_failed" if migration["phase"] == "failed" else "storage_preparation"
        samples = []
        for sample in [*history, status]:
            item = sample.get("storage_migration") or {}
            try:
                when = datetime.fromisoformat(sample["observed_at"])
                if now - timedelta(minutes=5) <= when <= now and item.get("phase") == "copying":
                    samples.append((when, item["copied_bytes"]))
            except (KeyError, TypeError, ValueError):
                continue
        samples.sort()
        if len(samples) >= 2:
            duration = (samples[-1][0] - samples[0][0]).total_seconds()
            progress = samples[-1][1] - samples[0][1]
            if duration >= 60 and progress > 0:
                rate = progress / duration
                remaining = max(0, migration.get("total_bytes", 0) - migration.get("copied_bytes", 0))
                result.update(copy_rate_bytes_per_second=round(rate), copy_eta_seconds=round(remaining / rate),
                              copy_eta_caveat="Transfer only; verification, startup and chain catch-up are additional.")
        return dict(result, state=state)
    if status.get("head_age_seconds") is None or int(status.get("block", "0x0"), 16) == 0:
        return dict(result, state="waiting_for_rpc_head")
    if status["head_age_seconds"] <= 300:
        return dict(result, state="near_head_waiting_confirmation")
    start = now - timedelta(hours=12)
    if migration.get("observed_at"):
        start = max(start, datetime.fromisoformat(migration["observed_at"]))
    points = []
    for sample in [*history, status]:
        try:
            when = datetime.fromisoformat(sample["observed_at"])
            age = sample.get("head_age_seconds")
            block = int(sample.get("block", "0x0"), 16)
            pid = ((status.get('activity') or {}).get('process') or {}).get('pid')
            sample_pid = ((sample.get('activity') or {}).get('process') or {}).get('pid')
            if (start <= when <= now and isinstance(age, (int, float)) and age >= 0 and block > 0
                    and (pid is None or sample_pid == pid)):
                points.append((when, age, block))
        except (ValueError, TypeError, KeyError):
            continue
    points.sort()
    transitions = []
    for point in points:
        if not transitions or point[2] != transitions[-1][2]:
            transitions.append(point)
    # The first sample may start halfway through a batch. Exclude that interval,
    # and require two complete publication-to-publication cycles.
    if len(transitions) < 4:
        return dict(result, state="waiting_for_validated_progress")
    transitions = transitions[1:]
    cycles = list(zip(transitions, transitions[1:]))
    if any(right[2] <= left[2] for left, right in cycles):
        return dict(result, state='head_reorganization_collect_new_samples')
    first, last = transitions[0], transitions[-1]
    duration = (last[0] - first[0]).total_seconds()
    if duration < 120:
        return dict(result, state="collecting_rate_samples")
    if (now - last[0]).total_seconds() > max(1800, 2 * max(
            (right[0] - left[0]).total_seconds() for left, right in cycles)):
        return dict(result, state='stale_cycle_estimate_inspect_activity')
    catchup = (first[1] - last[1]) / duration
    rates = [(left[1] - right[1]) / (right[0] - left[0]).total_seconds()
             for left, right in cycles if right[0] > left[0]]
    result.update(window_seconds=duration, validated_blocks=last[2] - first[2],
                  complete_cycles=len(cycles),
                  lag_reduction_seconds_per_second=round(catchup, 4))
    if catchup <= 0:
        return dict(result, state="no_catchup_observed")
    eta = max(0, (status["head_age_seconds"] - 300) / catchup)
    finish = now + timedelta(seconds=eta)
    scenarios = {}
    for name, rate in (('optimistic', max(rates)), ('central', catchup), ('pessimistic', min(rates))):
        seconds = max(0, (status['head_age_seconds'] - 300) / rate) if rate > 0 else None
        scenarios[name] = {'eta_seconds': round(seconds) if seconds is not None else None,
                           'finish_utc': (now + timedelta(seconds=seconds)).astimezone(timezone.utc).isoformat()
                           if seconds is not None else None}
    return dict(result, state="conditional_estimate", eta_seconds=round(eta),
                scenarios=scenarios,
                estimated_finish_utc=finish.astimezone(timezone.utc).isoformat(),
                on_track_estimate=finish <= end,
                caveat="Scenarios use complete validated cycles from the current process. Pending execution is not credited. No statistical probability; final RPC confirmation is required.")
