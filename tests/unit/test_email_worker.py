from worker import email_worker


def test_process_batch_returns_processed_count(app, monkeypatch):
    monkeypatch.setattr(
        "worker.email_worker.notification_service.process_queued",
        lambda limit: {"processed": 3, "sent": 2, "failed": 1},
    )
    processed = email_worker._process_batch(app)
    assert processed == 3


def test_run_worker_sleeps_when_nothing_processed(monkeypatch):
    calls = {"count": 0, "sleep": 0}

    class _FakeLogger:
        def info(self, *_args, **_kwargs):
            return None

    class _FakeApp:
        logger = _FakeLogger()

    def fake_create_app():
        return _FakeApp()

    def fake_process_batch(_app):
        calls["count"] += 1
        return 0

    def fake_sleep(_seconds):
        calls["sleep"] += 1
        raise RuntimeError("stop_worker_loop")

    monkeypatch.setattr("worker.email_worker.create_app", fake_create_app)
    monkeypatch.setattr("worker.email_worker._process_batch", fake_process_batch)
    monkeypatch.setattr("worker.email_worker.time.sleep", fake_sleep)

    try:
        email_worker.run_worker()
    except RuntimeError as exc:
        assert str(exc) == "stop_worker_loop"

    assert calls["count"] == 1
    assert calls["sleep"] == 1
