from __future__ import annotations

import time
import threading
from typing import List, Dict, Any

import requests

from config import SECONDARY_RATE_SLEEP_SECS, RETRY_SLEEP_SECS, MAX_API_RETRIES

GRAPHQL_URL = "https://api.github.com/graphql"

PR_QUERY = """
query($owner:String!, $name:String!, $number:Int!) {
  repository(owner:$owner, name:$name) {
    nameWithOwner
    isArchived
    isFork
    stargazerCount
    forkCount
    defaultBranchRef { name }
    primaryLanguage { name }

    pullRequest(number:$number) {
      number
      state
      mergeable
      createdAt
      closedAt
      mergedAt
      additions
      deletions
      changedFiles
      commits { totalCount }

      baseRefName
      headRefName
      baseRefOid
      headRefOid
      mergeCommit { oid }
    }
  }
}
"""


class GitHubTokenPool:
    def __init__(self, tokens: List[str]):
        if not tokens:
            raise ValueError("No GitHub tokens provided")
        self.tokens = tokens
        self.lock = threading.Lock()
        self.index = 0

    def _next_token(self) -> str:
        with self.lock:
            t = self.tokens[self.index]
            self.index = (self.index + 1) % len(self.tokens)
        return t

    def graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Robust GraphQL requester with token rotation and bounded retries.
        Raises RuntimeError on repeated failure.
        """
        last_err: str = ""

        for attempt in range(1, MAX_API_RETRIES + 1):
            token = self._next_token()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

            try:
                r = requests.post(
                    GRAPHQL_URL,
                    headers=headers,
                    json={"query": query, "variables": variables},
                    timeout=30,
                )
            except requests.RequestException as e:
                last_err = f"request_exception: {type(e).__name__}: {str(e)[:200]}"
                time.sleep(RETRY_SLEEP_SECS)
                continue

            body_lower = (r.text or "").lower()

            # GitHub secondary rate limit
            if r.status_code == 403 and "secondary rate limit" in body_lower:
                last_err = "secondary_rate_limit"
                time.sleep(SECONDARY_RATE_SLEEP_SECS)
                continue

            # Abuse detection / general 403 sometimes transient
            if r.status_code in (429, 502, 503, 504):
                last_err = f"transient_http_{r.status_code}"
                time.sleep(RETRY_SLEEP_SECS)
                continue

            if r.status_code == 200:
                data = r.json()
                if "errors" in data:
                    # GraphQL errors could be permanent (e.g., not found) or transient.
                    # We bubble up as RuntimeError and let extractor label ERR_GH_API.
                    raise RuntimeError(str(data["errors"])[:500])
                return data

            # Other non-200s: capture and retry a bit
            last_err = f"http_{r.status_code}: {(r.text or '')[:200]}"
            time.sleep(RETRY_SLEEP_SECS)

        raise RuntimeError(f"graphql_failed_after_{MAX_API_RETRIES}_attempts: {last_err}")

    def fetch_repo_and_pr(self, owner: str, name: str, number: int) -> Dict[str, Any]:
        return self.graphql(PR_QUERY, {"owner": owner, "name": name, "number": number})
