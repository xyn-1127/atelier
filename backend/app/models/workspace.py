from datetime import datetime                                                                                                      
                
from sqlalchemy import String, Text, DateTime, func                                                                                
from sqlalchemy.orm import Mapped, mapped_column, relationship
                                                                                                                                    
from app.db.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"
                                                                                                                                    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))                                                                                 
    path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    index_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())                                              
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
                                                                                                                                    
    files = relationship("File", back_populates="workspace", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="workspace", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="workspace", cascade="all, delete-orphan")