import logging

logger = logging.getLogger("ingestion.resume_merger")


def merge_resume_with_query(resume_text: str, user_query: str) -> str:
    """
    Merges parsed resume content with the user's free-text query into a
    single enriched string that the ProfileUnderstandingAgent can parse.

    The ProfileUnderstandingAgent's existing extraction prompt handles this
    format without any prompt changes — the RESUME CONTEXT block provides
    grounded facts while the USER QUERY captures the stated goal.

    Args:
        resume_text: Cleaned plain text extracted from the resume.
        user_query: The user's free-text career question or goal statement.

    Returns:
        A single merged string with labelled sections.
    """
    merged = (
        f"RESUME CONTEXT:\n"
        f"{resume_text.strip()}\n\n"
        f"USER QUERY:\n"
        f"{user_query.strip()}"
    )
    logger.info(
        f"Merged resume ({len(resume_text)} chars) with query ({len(user_query)} chars) "
        f"into enriched input ({len(merged)} chars)."
    )
    return merged
