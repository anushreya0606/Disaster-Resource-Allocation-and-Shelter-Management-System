class TriageService:
    """
    Calculates the priority score of an evacuee
    based on medical urgency and vulnerability.
    """

    # Medical urgency scores
    MEDICAL_SCORES = {
        "CRITICAL": 50,
        "HIGH": 40,
        "MEDIUM": 25,
        "LOW": 10,
        "NONE": 0
    }

    # Vulnerability scores
    VULNERABILITY_SCORES = {
        "PREGNANT": 30,
        "ELDERLY": 25,
        "CHILD": 25,
        "DISABLED": 25,
        "NONE": 0
    }

    @classmethod
    def calculate_priority(
        cls,
        medical_condition: str | None,
        vulnerability_status: str | None,
        age: int | None = None
    ) -> int:
        """
        Calculate the total priority score.

        Priority =
            Medical urgency
            + Vulnerability
            + Age-based priority
        """

        medical = cls._normalize(medical_condition)
        vulnerability = cls._normalize(vulnerability_status)

        medical_score = cls.MEDICAL_SCORES.get(medical, 0)

        vulnerability_score = cls.VULNERABILITY_SCORES.get(
            vulnerability,
            0
        )

        age_score = cls._calculate_age_score(age)

        return medical_score + vulnerability_score + age_score

    @staticmethod
    def _calculate_age_score(age: int | None) -> int:
        """
        Give additional priority to very young children
        and elderly evacuees.

        Vulnerability status should still be used for
        the main vulnerability classification.
        """

        if age is None:
            return 0

        if age <= 5:
            return 15

        if age >= 75:
            return 15

        return 0

    @staticmethod
    def _normalize(value: str | None) -> str:
        """
        Normalize input so that values such as
        'critical', 'Critical', and ' CRITICAL '
        are treated the same way.
        """

        if not value:
            return "NONE"

        return value.strip().upper()