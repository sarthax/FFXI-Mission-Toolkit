"""Evidence-aware research services."""
from .session import PERMISSION_PROFILES, ResearchSession, ResearchSessionStore
from .tools import (
    ACCESS_PROPOSE,
    ACCESS_READ,
    ACCESS_VALIDATE,
    ResearchTool,
    ResearchToolRegistry,
    register_legacy_db_tools,
)

__all__=[
    "PERMISSION_PROFILES",
    "ResearchSession",
    "ResearchSessionStore",
    "ACCESS_READ",
    "ACCESS_PROPOSE",
    "ACCESS_VALIDATE",
    "ResearchTool",
    "ResearchToolRegistry",
    "register_legacy_db_tools",
]

from .crawler import BoundedSourceCrawler, CrawlPolicy

from .runner import ResearchRunner

from .domain_tools import WorkbenchDomainReader

from .extended_tools import CaptureResearchReader, ReferenceResearchReader, ClientResearchReader

from .proposal_verifier import ProposalVerifier
from .proposal_tools import ProposalResearchService

from .client_binary_tools import ClientBinaryResearchReader
