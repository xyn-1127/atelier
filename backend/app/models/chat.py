from datetime import datetime
                                                                                                                                    
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship                                                                     
                
from app.db.base import Base


class Chat(Base):
    __tablename__ = "chats"
                                                                                                                                    
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))                                                         
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compacted_count: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())                                              
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
                                                                                                                                    
    workspace = relationship("Workspace", back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")             