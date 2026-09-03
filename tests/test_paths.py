from che_core.paths import _slugify, resolve_worktree_slug


def test_slugify_basic():
    assert _slugify("Manifesto 48 Projetos") == "Manifesto-48-Projetos"
    assert _slugify("feat/FLO-513/process refund") == "feat--FLO-513--process-refund"
    assert _slugify("vc-educar/corp-website") == "vc-educar--corp-website"
    assert _slugify("main") == "main"
    assert _slugify("---test---") == "test"
    assert _slugify("a___b") == "a___b"  # Allows underscores


def test_resolve_worktree_slug(tmp_path):
    """Test standard repo resolution"""
    # Create a mock git repo structure
    repo_dir = tmp_path / "my-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    # We mock the git branch resolution since we can't easily mock subprocess here
    # without pytest-mock, but we can test the fallback

    slug = resolve_worktree_slug(str(repo_dir))
    # It should fallback to main if git fails/is not mocked
    assert slug == "my-repo__main"


def test_resolve_worktree_slug_worktrees(tmp_path):
    """Test git worktree structure resolution"""
    worktrees_dir = tmp_path / "my-repo.worktrees"
    worktrees_dir.mkdir()

    feature_dir = worktrees_dir / "feat-FLO-513"
    feature_dir.mkdir()

    slug = resolve_worktree_slug(str(feature_dir))
    assert slug == "my-repo__feat-FLO-513"
