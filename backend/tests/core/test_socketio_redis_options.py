from app.core.socketio_redis import (
    get_socketio_redis_listener_options,
    get_socketio_redis_publisher_options,
)


def test_socketio_listener_redis_options_disable_read_timeout() -> None:
    options = get_socketio_redis_listener_options()

    assert options["socket_connect_timeout"] == 5
    assert options["socket_timeout"] is None
    assert options["socket_keepalive"] is True


def test_socketio_publisher_redis_options_keep_request_timeout_scope() -> None:
    options = get_socketio_redis_publisher_options()

    assert options["socket_connect_timeout"] == 5
    assert options["socket_keepalive"] is True
    assert "socket_timeout" not in options
