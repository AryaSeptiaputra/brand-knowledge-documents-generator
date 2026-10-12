"""Create deterministic completeness suggestions from available brand facts."""

from brand_docs.domain.models import BrandData, CompletenessSuggestion
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)
EXPECTED_GENERAL_KEYS = frozenset({"retur", "pengiriman", "pembayaran", "garansi", "kontak"})


class CompletenessAdvisor:
    """Suggest common sections that are absent from the user's YAML."""

    def suggest(self, brand: BrandData) -> list[CompletenessSuggestion]:
        present = {fact.path.split(".")[0].lower() for fact in brand.facts if fact.product is None}
        missing = sorted(EXPECTED_GENERAL_KEYS - present)
        return [
            CompletenessSuggestion(
                message=(
                    f"Consider adding {key.replace('_', ' ')} information "
                    "if it applies to your brand."
                ),
                related_path=key,
            )
            for key in missing
        ]
