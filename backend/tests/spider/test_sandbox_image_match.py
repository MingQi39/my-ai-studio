from types import SimpleNamespace
from unittest.mock import MagicMock

import app.spider.services.sandbox as sandbox_mod
from app.spider.services.sandbox import (
    _container_matches_configured_image,
    _create_session_container,
    _find_session_container,
    container_name_for_session,
    remove_session_sandbox,
)


def test_container_name_for_session_is_compose_style():
    name = container_name_for_session("9cdbb3f8-2d74-48ff-a4d9-c72b06ad3494")
    assert name.startswith("my-ai-studio-spider-")
    assert "9cdbb3f8" in name


def test_container_matches_configured_image_true():
    image = SimpleNamespace(id="sha256:abc")
    client = SimpleNamespace(images=SimpleNamespace(get=lambda _name: image))
    container = SimpleNamespace(image=image)
    assert _container_matches_configured_image(client, container, "playwright:tag") is True


def test_find_session_container_removes_stale_image(monkeypatch):
    monkeypatch.setattr(sandbox_mod.settings, "SPIDER_DOCKER_IMAGE", "playwright:new")

    stale = MagicMock()
    stale.status = "running"
    stale.image = SimpleNamespace(id="sha256:old")
    stale.remove = MagicMock()

    expected = SimpleNamespace(id="sha256:new")

    class NotFound(Exception):
        pass

    monkeypatch.setattr(sandbox_mod, "NotFound", NotFound)

    client = MagicMock()
    client.containers.list.return_value = [stale]
    client.images.get.return_value = expected

    assert _find_session_container(client, "sess-1") is None
    stale.remove.assert_called_once_with(force=True)


def test_create_session_container_sets_name_and_compose_labels(monkeypatch):
    monkeypatch.setattr(sandbox_mod.settings, "SPIDER_DOCKER_IMAGE", "playwright:jammy")
    monkeypatch.setattr(sandbox_mod.settings, "SPIDER_DOCKER_MEMORY_LIMIT", "2g")
    monkeypatch.setattr(sandbox_mod.settings, "SPIDER_DOCKER_CPU_QUOTA", 100000)

    created = SimpleNamespace(id="cid-1")
    client = MagicMock()
    client.containers.run.return_value = created

    cid = _create_session_container(
        client,
        volume_name="spider-user-sess",
        mount_path="/workspace",
        user_id="user-1",
        session_id="sess-1",
    )
    assert cid == "cid-1"
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["name"] == container_name_for_session("sess-1")
    assert kwargs["labels"]["com.docker.compose.project"] == "my-ai-studio"
    assert kwargs["labels"]["com.docker.compose.service"] == "spider"
    assert kwargs["labels"]["spider.session_id"] == "sess-1"


def test_remove_session_sandbox_force_removes_by_label(monkeypatch):
    container = MagicMock()
    client = MagicMock()
    client.containers.list.return_value = [container]
    fake_docker = MagicMock()
    fake_docker.from_env.return_value = client
    monkeypatch.setattr(sandbox_mod, "docker", fake_docker)

    remove_session_sandbox("sess-1")
    client.containers.list.assert_called_once_with(
        all=True, filters={"label": "spider.session_id=sess-1"}
    )
    container.remove.assert_called_once_with(force=True)
