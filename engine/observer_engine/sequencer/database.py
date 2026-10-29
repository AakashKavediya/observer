"""
observer_engine.sequencer.database
Local SQLite database manager for Track 2 (Task Sequencer).
Persists conversations, messages, micro-tasks, feedback, and user preferences.
Zero cloud dependencies, zero external network calls.
"""

import os
import sqlite3
import json
import time
import uuid
from typing import List, Optional, Dict, Any

from observer_engine.sequencer.models import (
    ConversationMessage,
    ConversationSummary,
    TaskRecord,
    MicroStep,
    FeedbackRecord,
    UserPreferences,
    SequencerResponseContract,
)
from observer_engine.sequencer.config import SEQUENCER_CONFIG


class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or SEQUENCER_CONFIG.database_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Conversations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            # Messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    content TEXT NOT NULL,
                    contract_json TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)
            # Tasks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    current_micro_step_json TEXT,
                    step_history_json TEXT,
                    energy_level_reported INTEGER DEFAULT 3,
                    deadline TEXT,
                    planner_task_id TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            # Feedback
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    step_id TEXT,
                    feedback_type TEXT NOT NULL,
                    user_comment TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            # User Preferences
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                )
            """)
            conn.commit()

    # -------------------------------------------------------------
    # Conversations
    # -------------------------------------------------------------
    def create_conversation(self, title: str = "New Task Support") -> ConversationSummary:
        conv_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conv_id, title, now, now),
            )
            conn.commit()
        return ConversationSummary(id=conv_id, title=title, message_count=0, created_at=now, updated_at=now)

    def list_conversations(self) -> List[ConversationSummary]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT c.id, c.title, c.created_at, c.updated_at, COUNT(m.id) as msg_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            """).fetchall()

            return [
                ConversationSummary(
                    id=row["id"],
                    title=row["title"],
                    message_count=row["msg_count"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_conversation_messages(self, conversation_id: str) -> List[ConversationMessage]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT id, conversation_id, sender, content, contract_json, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,),
            ).fetchall()

            messages = []
            for r in rows:
                contract = None
                if r["contract_json"]:
                    try:
                        contract = SequencerResponseContract.model_validate_json(r["contract_json"])
                    except Exception:
                        pass
                messages.append(
                    ConversationMessage(
                        id=r["id"],
                        conversation_id=r["conversation_id"],
                        sender=r["sender"],
                        content=r["content"],
                        contract=contract,
                        created_at=r["created_at"],
                    )
                )
            return messages

    def save_message(
        self,
        conversation_id: str,
        sender: str,
        content: str,
        contract: Optional[SequencerResponseContract] = None,
    ) -> ConversationMessage:
        msg_id = f"msg_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}"
        now = time.time()
        contract_json = contract.model_dump_json() if contract else None

        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, conversation_id, sender, content, contract_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (msg_id, conversation_id, sender, content, contract_json, now),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            conn.commit()

        return ConversationMessage(
            id=msg_id,
            conversation_id=conversation_id,
            sender=sender,
            content=content,
            contract=contract,
            created_at=now,
        )

    def rename_conversation(self, conversation_id: str, new_title: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (new_title, time.time(), conversation_id),
            )
            conn.commit()

    def delete_conversation(self, conversation_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM tasks WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()

    def clear_all(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM conversations")
            conn.execute("DELETE FROM feedback")
            conn.commit()

    # -------------------------------------------------------------
    # Tasks & Micro-steps
    # -------------------------------------------------------------
    def save_or_update_task(self, task: TaskRecord, conversation_id: Optional[str] = None) -> TaskRecord:
        now = time.time()
        task.updated_at = now
        curr_step_json = task.current_micro_step.model_dump_json() if task.current_micro_step else None
        history_json = json.dumps([s.model_dump() for s in task.step_history])

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, conversation_id, title, description, status,
                    current_micro_step_json, step_history_json, energy_level_reported,
                    deadline, planner_task_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    status = excluded.status,
                    current_micro_step_json = excluded.current_micro_step_json,
                    step_history_json = excluded.step_history_json,
                    energy_level_reported = excluded.energy_level_reported,
                    deadline = excluded.deadline,
                    planner_task_id = excluded.planner_task_id,
                    updated_at = excluded.updated_at
            """, (
                task.task_id,
                conversation_id,
                task.title,
                task.description,
                task.status,
                curr_step_json,
                history_json,
                task.energy_level_reported,
                task.deadline,
                task.planner_task_id,
                task.created_at,
                task.updated_at,
            ))
            conn.commit()

        return task

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None

            curr_step = None
            if row["current_micro_step_json"]:
                try:
                    curr_step = MicroStep.model_validate_json(row["current_micro_step_json"])
                except Exception:
                    pass

            step_history = []
            if row["step_history_json"]:
                try:
                    raw_steps = json.loads(row["step_history_json"])
                    step_history = [MicroStep.model_validate(s) for s in raw_steps]
                except Exception:
                    pass

            return TaskRecord(
                task_id=row["task_id"],
                title=row["title"],
                description=row["description"] or "",
                status=row["status"],
                current_micro_step=curr_step,
                step_history=step_history,
                energy_level_reported=row["energy_level_reported"],
                deadline=row["deadline"],
                planner_task_id=row["planner_task_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_latest_task_for_conversation(self, conversation_id: str) -> Optional[TaskRecord]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT task_id FROM tasks WHERE conversation_id = ? ORDER BY updated_at DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if row:
                return self.get_task(row["task_id"])
            return None

    # -------------------------------------------------------------
    # Feedback
    # -------------------------------------------------------------
    def record_feedback(
        self,
        conversation_id: str,
        feedback_type: str,
        step_id: Optional[str] = None,
        user_comment: Optional[str] = None,
    ) -> FeedbackRecord:
        fb_id = f"fb_{int(time.time()*1000)}_{uuid.uuid4().hex[:4]}"
        now = time.time()
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO feedback (feedback_id, conversation_id, step_id, feedback_type, user_comment, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (fb_id, conversation_id, step_id, feedback_type, user_comment, now),
            )
            conn.commit()
        return FeedbackRecord(
            feedback_id=fb_id,
            conversation_id=conversation_id,
            step_id=step_id,
            feedback_type=feedback_type,
            user_comment=user_comment,
            timestamp=now,
        )

    # -------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------
    def get_preferences(self) -> UserPreferences:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value_json FROM user_preferences WHERE key = 'preferences'").fetchone()
            if row:
                try:
                    return UserPreferences.model_validate_json(row["value_json"])
                except Exception:
                    pass
            return UserPreferences()

    def update_preferences(self, prefs: UserPreferences) -> UserPreferences:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_preferences (key, value_json) VALUES ('preferences', ?)",
                (prefs.model_dump_json(),),
            )
            conn.commit()
        return prefs
