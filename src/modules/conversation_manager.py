"""
對話管理器模組

負責管理聊天式AI Agent的對話歷史、上下文追蹤、智能建議生成等功能。

Author: Leon Lu
Created: 2025-01-25
"""

import logging
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """訊息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(Enum):
    """訊息類型"""
    TEXT = "text"
    QUERY_RESULT = "query_result"
    SUGGESTION = "suggestion"
    ERROR = "error"
    TYPING = "typing"


@dataclass
class ChatMessage:
    """聊天訊息"""
    id: str
    role: MessageRole
    content: str
    message_type: MessageType
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatMessage':
        """從字典創建ChatMessage"""
        return cls(
            id=data['id'],
            role=MessageRole(data['role']),
            content=data['content'],
            message_type=MessageType(data['message_type']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            metadata=data.get('metadata')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'id': self.id,
            'role': self.role.value,
            'content': self.content,
            'message_type': self.message_type.value,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


@dataclass
class ConversationContext:
    """對話上下文"""
    last_query: Optional[str] = None
    last_sql: Optional[str] = None
    last_results: Optional[Dict[str, Any]] = None
    mentioned_patients: List[str] = None
    current_topic: Optional[str] = None
    session_stats: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.mentioned_patients is None:
            self.mentioned_patients = []
        if self.session_stats is None:
            self.session_stats = {
                'total_queries': 0,
                'successful_queries': 0,
                'topics_discussed': []
            }


class ConversationManager:
    """對話管理器"""
    
    def __init__(self, max_history: int = 50, context_window: int = 10):
        """
        初始化對話管理器
        
        Args:
            max_history: 最大歷史記錄數
            context_window: 上下文窗口大小
        """
        self.max_history = max_history
        self.context_window = context_window
        self.messages: List[ChatMessage] = []
        self.context = ConversationContext()
        
        # 智能建議生成器
        self.suggestion_templates = {
            'patient_query': [
                "查看{patient}的最近檢驗結果",
                "分析{patient}的用藥歷史",
                "檢視{patient}的就診趨勢"
            ],
            'lab_results': [
                "分析這些檢驗值的正常範圍",
                "查看相關檢驗項目的趨勢",
                "比較不同時期的檢驗結果"
            ],
            'medication': [
                "查看此藥物的其他處方記錄",
                "分析藥物使用的頻率分布",
                "檢查藥物交互作用風險"
            ],
            'diagnosis': [
                "查看相同診斷的其他案例",
                "分析診斷的時間分布",
                "查看相關的檢驗項目"
            ]
        }
        
        logger.info("對話管理器已初始化")
    
    def add_message(self, role: MessageRole, content: str, 
                   message_type: MessageType = MessageType.TEXT,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        添加訊息到對話歷史
        
        Args:
            role: 訊息角色
            content: 訊息內容
            message_type: 訊息類型
            metadata: 元數據
            
        Returns:
            str: 訊息ID
        """
        message_id = self._generate_message_id()
        
        message = ChatMessage(
            id=message_id,
            role=role,
            content=content,
            message_type=message_type,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        
        self.messages.append(message)
        
        # 更新上下文
        self._update_context(message)
        
        # 清理舊訊息
        self._cleanup_history()
        
        logger.debug(f"已添加訊息: {message_id} ({role.value})")
        return message_id
    
    def get_conversation_history(self, limit: Optional[int] = None) -> List[ChatMessage]:
        """
        獲取對話歷史
        
        Args:
            limit: 限制返回的訊息數量
            
        Returns:
            List[ChatMessage]: 對話歷史
        """
        messages = self.messages
        if limit:
            messages = messages[-limit:]
        return messages
    
    def get_context_for_llm(self) -> str:
        """
        獲取用於LLM的上下文字串
        
        Returns:
            str: 格式化的上下文
        """
        context_parts = []
        
        # 獲取最近的對話
        recent_messages = self.messages[-self.context_window:]
        
        if recent_messages:
            context_parts.append("最近的對話：")
            for msg in recent_messages:
                if msg.role in [MessageRole.USER, MessageRole.ASSISTANT]:
                    context_parts.append(f"{msg.role.value}: {msg.content[:200]}")
        
        # 添加當前上下文資訊
        if self.context.last_query:
            context_parts.append(f"上次查詢：{self.context.last_query}")
        
        if self.context.mentioned_patients:
            patients = ", ".join(self.context.mentioned_patients[-3:])  # 最近3個病患
            context_parts.append(f"討論過的病患：{patients}")
        
        if self.context.current_topic:
            context_parts.append(f"當前話題：{self.context.current_topic}")
        
        return "\n".join(context_parts)
    
    def generate_suggestions(self, last_result: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        生成智能建議
        
        Args:
            last_result: 最後的查詢結果
            
        Returns:
            List[str]: 建議列表
        """
        suggestions = []
        
        try:
            # 基於最後查詢結果生成建議
            if last_result and last_result.get('success'):
                query_type = last_result.get('query_type', 'unknown')
                sql_query = last_result.get('sql_query', '')
                
                # 根據查詢類型生成建議
                if 'patient' in query_type.lower() or 'kcstmr' in sql_query:
                    suggestions.extend(self._get_patient_suggestions(last_result))
                elif 'lab' in query_type.lower() or 'CO18H' in sql_query:
                    suggestions.extend(self._get_lab_suggestions())
                elif 'prescription' in query_type.lower() or 'CO02M' in sql_query:
                    suggestions.extend(self._get_medication_suggestions())
                elif 'visit' in query_type.lower() or 'CO03M' in sql_query:
                    suggestions.extend(self._get_diagnosis_suggestions())
            
            # 基於對話歷史生成建議
            if self.context.mentioned_patients:
                patient = self.context.mentioned_patients[-1]  # 最近提到的病患
                suggestions.append(f"查看{patient}的完整病歷摘要")
            
            # 通用建議
            if not suggestions:
                suggestions = [
                    "查詢特定病患的基本資料",
                    "分析最近一週的就診統計",
                    "查看常用檢驗項目的結果分布",
                    "統計常見診斷的出現頻率"
                ]
            
        except Exception as e:
            logger.error(f"生成建議時發生錯誤: {e}")
            suggestions = ["需要什麼幫助嗎？"]
        
        return suggestions[:3]  # 最多返回3個建議
    
    def extract_patient_names(self, text: str) -> List[str]:
        """
        從文本中提取病患姓名
        
        Args:
            text: 輸入文本
            
        Returns:
            List[str]: 提取的姓名列表
        """
        import re
        
        # 簡單的中文姓名匹配（2-4個中文字符）
        pattern = r'[\u4e00-\u9fff]{2,4}(?=的|之|病患|先生|小姐|女士)'
        names = re.findall(pattern, text)
        
        # 去除重複並添加到上下文
        unique_names = list(set(names))
        for name in unique_names:
            if name not in self.context.mentioned_patients:
                self.context.mentioned_patients.append(name)
        
        return unique_names
    
    def clear_conversation(self):
        """清空對話記錄"""
        self.messages.clear()
        self.context = ConversationContext()
        logger.info("對話記錄已清空")
    
    def export_conversation(self) -> Dict[str, Any]:
        """
        導出對話記錄
        
        Returns:
            Dict[str, Any]: 對話記錄
        """
        return {
            'messages': [msg.to_dict() for msg in self.messages],
            'context': asdict(self.context),
            'timestamp': datetime.now().isoformat()
        }
    
    def import_conversation(self, data: Dict[str, Any]):
        """
        導入對話記錄
        
        Args:
            data: 對話記錄數據
        """
        try:
            self.messages = [ChatMessage.from_dict(msg_data) for msg_data in data['messages']]
            self.context = ConversationContext(**data['context'])
            logger.info(f"已導入{len(self.messages)}條對話記錄")
        except Exception as e:
            logger.error(f"導入對話記錄失敗: {e}")
            raise
    
    def _generate_message_id(self) -> str:
        """生成訊息ID"""
        timestamp = str(time.time())
        return hashlib.md5(timestamp.encode()).hexdigest()[:8]
    
    def _update_context(self, message: ChatMessage):
        """更新對話上下文"""
        if message.role == MessageRole.USER:
            # 提取病患姓名
            self.extract_patient_names(message.content)
            
            # 更新統計
            self.context.session_stats['total_queries'] += 1
            
        elif message.role == MessageRole.ASSISTANT:
            # 更新查詢相關資訊
            if message.metadata:
                if 'sql_query' in message.metadata:
                    self.context.last_sql = message.metadata['sql_query']
                if 'query_result' in message.metadata:
                    self.context.last_results = message.metadata['query_result']
                    if message.metadata['query_result'].get('success'):
                        self.context.session_stats['successful_queries'] += 1
    
    def _cleanup_history(self):
        """清理歷史記錄"""
        if len(self.messages) > self.max_history:
            # 保留最近的記錄
            self.messages = self.messages[-self.max_history:]
            logger.debug("已清理舊的對話記錄")
    
    def _get_patient_suggestions(self, result: Dict[str, Any]) -> List[str]:
        """獲取病患相關建議"""
        if self.context.mentioned_patients:
            patient = self.context.mentioned_patients[-1]
            return [
                f"查看{patient}的最近檢驗結果",
                f"分析{patient}的用藥歷史"
            ]
        return []
    
    def _get_lab_suggestions(self) -> List[str]:
        """獲取檢驗相關建議"""
        return [
            "分析這些檢驗值的正常範圍",
            "查看相關檢驗項目的趨勢"
        ]
    
    def _get_medication_suggestions(self) -> List[str]:
        """獲取用藥相關建議"""
        return [
            "查看此藥物的其他處方記錄",
            "分析藥物使用的頻率分布"
        ]
    
    def _get_diagnosis_suggestions(self) -> List[str]:
        """獲取診斷相關建議"""
        return [
            "查看相同診斷的其他案例",
            "分析診斷的時間分布"
        ]


# 創建全局對話管理器實例
conversation_manager = ConversationManager()