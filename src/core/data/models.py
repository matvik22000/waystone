from sqlalchemy import (
    DateTime,
    Float,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional


class Base(DeclarativeBase):
    pass


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    destination: Mapped[str] = mapped_column(String(70), unique=True, nullable=False)
    dst: Mapped[str] = mapped_column(String(64), nullable=False)
    identity: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_nodes_identity", "identity"),
        Index("idx_nodes_time", "time"),
    )


class Peer(Base):
    __tablename__ = "peers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    destination: Mapped[str] = mapped_column(String(70), unique=True, nullable=False)
    dst: Mapped[str] = mapped_column(String(64), nullable=False)
    identity: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_peers_identity", "identity"),
        Index("idx_peers_time", "time"),
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    target_address: Mapped[str] = mapped_column(String(32), nullable=False)
    src_address: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("target_address", "src_address", name="uq_citations_target_src"),
        Index("idx_citations_target", "target_address"),
        Index("idx_citations_src", "src_address"),
    )


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (Index("idx_search_queries_created", "created_at"),)


class UserSearchHistory(Base):
    __tablename__ = "user_search_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    remote_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("idx_user_search_history_identity", "remote_identity"),
        Index("idx_user_search_history_time", "remote_identity", "time"),
    )
