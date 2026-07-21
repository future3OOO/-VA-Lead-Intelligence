from enum import Enum


class MembershipRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LeadStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPPRESSED = "suppressed"
    EXPORTED = "exported"


class ReviewDecision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class ExportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OutcomeType(str, Enum):
    CONTACTED = "contacted"
    RESPONDED = "responded"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    UNINTERESTED = "uninterested"
    BOUNCED = "bounced"


class CrawlStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class SourceType(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    COMPANY_WEB = "company_web"
    SEARCH = "search"


class IntentLabel(str, Enum):
    BUYER_REQUEST = "buyer_request"
    COMPANY_HIRING = "company_hiring"
    OPERATIONAL_PAIN = "operational_pain"
    GROWTH_TRIGGER = "growth_trigger"
    COMPANY_EXISTENCE_ONLY = "company_existence_only"
    SELLER_PROMOTION = "seller_promotion"
    JOB_SEEKER = "job_seeker"
    GENERAL_DISCUSSION = "general_discussion"
    UNRESOLVED = "unresolved"


class ContactRouteType(str, Enum):
    GENERIC_EMAIL = "generic_email"
    CONTACT_FORM = "contact_form"
    SALES_FORM = "sales_form"
    DEMO_BOOKING = "demo_booking"
    BUSINESS_PHONE = "business_phone"
    SUPPORT_ROUTE = "support_route"
    NAMED_WORK_EMAIL_APPROVED = "named_work_email_approved"
    SOCIAL_PROFILE_REVIEW_ONLY = "social_profile_review_only"
    NAMED_CONTACT = "named_contact"
