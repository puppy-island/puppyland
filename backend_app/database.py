import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pet_memorial.db")

def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    """Initialize database tables"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Pets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                breed TEXT,
                sound TEXT,
                color TEXT,
                gait TEXT,
                favorite_food TEXT,
                departure_way TEXT,
                personality TEXT,
                food_reaction TEXT,
                likes_clothes INTEGER DEFAULT 0,
                is_watchful INTEGER DEFAULT 0,
                is_clingy INTEGER DEFAULT 0,
                likes TEXT,
                fears TEXT,
                avatar_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Memories/Stories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                memory_type TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                media_url TEXT,
                trigger_npc INTEGER DEFAULT 0,
                collar_evolution INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
            )
        """)

        # Meeting stories table (相遇故事 - 记录与宠物相遇的故事)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL UNIQUE,
                story TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
            )
        """)

        # Virtual home items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_home_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_name TEXT NOT NULL,
                description TEXT,
                memory_id INTEGER,
                growth_level INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
                FOREIGN KEY (memory_id) REFERENCES memories(id) ON DELETE SET NULL
            )
        """)

        # Evolution records table (tracks NPC triggers, collar evolution, etc.)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evolution_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                evolution_type TEXT NOT NULL,
                description TEXT,
                previous_state TEXT,
                new_state TEXT,
                triggered_by_memory_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
                FOREIGN KEY (triggered_by_memory_id) REFERENCES memories(id) ON DELETE SET NULL
            )
        """)

        # Extended pet profiles (emotional dimensions)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pet_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL UNIQUE,
                hardest_moment TEXT,              -- TA离开后最难过的事
                regret TEXT,                      -- 遗憾
                fear_of_forgetting TEXT,          -- 最怕忘记TA什么
                wish_for_memorial_world TEXT,     -- 对记忆世界的愿望
                memory_to_preserve TEXT,          -- 最想保存的记忆
                memorial_way TEXT,                -- 纪念方式
                extra_data TEXT,                  -- JSON格式存储其他数据
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
            )
        """)

        # Chat messages with pet
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                role TEXT NOT NULL,               -- 'user' or 'pet'
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
            )
        """)

        # Pet animation state and position (for 2D world)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pet_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL UNIQUE,
                pos_x REAL DEFAULT 0,             -- X坐标（2D界面位置）
                pos_y REAL DEFAULT 0,             -- Y坐标
                pos_z REAL DEFAULT 0,             -- Z坐标（层级/高度）
                current_animation TEXT DEFAULT 'idle',  -- 当前动画状态: idle, walk, run, sit, lie, sleep, eat, bark, tail_wag, look_around, run_around, poop
                is_moving INTEGER DEFAULT 0,      -- 是否正在移动
                target_x REAL,                    -- 目标X坐标（移动中）
                target_y REAL,                    -- 目标Y坐标
                target_z REAL,                    -- 目标Z坐标
                move_speed REAL DEFAULT 100,      -- 移动速度（像素/秒）
                facing_direction TEXT DEFAULT 'right',  -- 朝向: left, right
                extra_data TEXT,                 -- JSON扩展数据
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
            )
        """)

        # Custom animations registry (用户自定义动画)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_animations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,        -- 动画名称，如 "happy_jump"
                display_name TEXT,                 -- 显示名称，如 "开心跳跃"
                description TEXT,                  -- 动画描述
                animation_url TEXT,                 -- 动画资源URL（前端使用）
                sprite_sheet_url TEXT,             -- 精灵图URL
                frame_count INTEGER DEFAULT 1,     -- 帧数
                frame_duration INTEGER DEFAULT 100, -- 每帧持续时间(ms)
                loop_count INTEGER DEFAULT -1,     -- 循环次数，-1表示无限循环
                category TEXT DEFAULT 'custom',    -- 分类: idle, action, emotion, special
                is_active INTEGER DEFAULT 1,      -- 是否启用
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Phase 1 场景记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scene_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                scene_type TEXT NOT NULL,         -- 场景类型: first_meeting/waiting_home/dining_together
                scene_name TEXT NOT NULL,         -- 场景名称
                description TEXT,                 -- 场景描述
                trigger_memory_id INTEGER,        -- 触发的记忆ID
                is_completed INTEGER DEFAULT 0,   -- 是否已完成
                completed_at TIMESTAMP,           -- 完成时间
                extra_data TEXT,                  -- JSON扩展数据
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
                FOREIGN KEY (trigger_memory_id) REFERENCES memories(id) ON DELETE SET NULL
            )
        """)

        # Phase 3 情感旅程表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journey_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                journey_type TEXT NOT NULL,       -- 旅程类型: continuation/new_memory/legacy
                title TEXT NOT NULL,              -- 旅程标题
                content TEXT,                     -- 旅程内容/故事
                based_on_memory_id INTEGER,       -- 基于的记忆ID
                next_suggestion TEXT,             -- 下一个建议/引导
                is_active INTEGER DEFAULT 1,      -- 是否活跃
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE,
                FOREIGN KEY (based_on_memory_id) REFERENCES memories(id) ON DELETE SET NULL
            )
        """)

        # 自然口述记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS narration_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                raw_text TEXT NOT NULL,           -- 用户原始输入
                parsed_memory_type TEXT,          -- 解析后的记忆类型
                parsed_title TEXT,                -- 解析后的标题
                parsed_content TEXT,              -- 解析后的内容
                generated_item_name TEXT,         -- 生成的物品名称
                generated_item_type TEXT,         -- 生成的物品类型
                ai_response TEXT,                 -- AI的回应/引导
                is_processed INTEGER DEFAULT 0,   -- 是否已处理
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
            )
        """)

        conn.commit()

def dict_from_row(row):
    """Convert sqlite Row to dictionary"""
    if row is None:
        return None
    return dict(row)

init_db()
