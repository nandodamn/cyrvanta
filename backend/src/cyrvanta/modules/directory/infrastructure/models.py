from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from cyrvanta.shared.database import Base


class DirectoryConfigurationModel(Base):
    __tablename__ = "directory_configurations"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id"), unique=True
    )
    provider_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    server_uri: Mapped[str] = mapped_column(String, nullable=False)
    use_starttls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_dn: Mapped[str] = mapped_column(String, nullable=False)
    bind_dn: Mapped[str] = mapped_column(String, nullable=False)
    bind_secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    user_filter: Mapped[str] = mapped_column(String, nullable=False)
    login_attribute: Mapped[str] = mapped_column(String, nullable=False)
    subject_attribute: Mapped[str] = mapped_column(String, nullable=False)
    email_attribute: Mapped[str] = mapped_column(String, nullable=False)
    display_name_attribute: Mapped[str] = mapped_column(String, nullable=False)
    group_base_dn: Mapped[str | None] = mapped_column(String)
    group_filter: Mapped[str | None] = mapped_column(String)
    group_attribute: Mapped[str | None] = mapped_column(String)
    ca_certificate_pem: Mapped[str | None] = mapped_column(Text)
    jit_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_success: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectoryIdentityModel(Base):
    __tablename__ = "directory_identities"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    provider_type: Mapped[str] = mapped_column(String, nullable=False)
    external_subject: Mapped[str] = mapped_column(String, nullable=False)
    normalized_username: Mapped[str] = mapped_column(String, nullable=False)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectoryGroupMappingModel(Base):
    __tablename__ = "directory_group_mappings"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("tenants.id"))
    external_group: Mapped[str] = mapped_column(String, nullable=False)
    role_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
