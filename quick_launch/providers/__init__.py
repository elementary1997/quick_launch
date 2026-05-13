from .base import Provider
from .github import GitHubProvider
from .bitbucket import BitbucketProvider
from .gitflic import GitFlicProvider
from .gitlab import GitLabProvider

PROVIDERS: list[type[Provider]] = [
    GitHubProvider,
    GitLabProvider,
    BitbucketProvider,
    GitFlicProvider,
]


def detect(url: str) -> Provider:
    for cls in PROVIDERS:
        if cls.matches(url):
            return cls(url)
    raise ValueError(f"Unknown repository host: {url}")
