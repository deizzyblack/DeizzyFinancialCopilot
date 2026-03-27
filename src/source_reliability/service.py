SOURCE_SCORES = {
    "trusted_api": 1.0,
    "known_user": 0.85,
    "manual_upload": 0.7,
    "unknown": 0.4,
}


class SourceReliabilityService:
    def __init__(self):
        self._user_trust: dict[str, float] = {}

    def register_user(self, user_id: str, trust_score: float) -> None:
        self._user_trust[user_id] = max(0.0, min(1.0, trust_score))

    def get_score(self, source_type: str = "manual_upload", user_id: str | None = None) -> float:
        if user_id and user_id in self._user_trust:
            return self._user_trust[user_id]
        return SOURCE_SCORES.get(source_type, SOURCE_SCORES["unknown"])
