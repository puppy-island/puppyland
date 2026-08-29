from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MemoryType(str, Enum):
    FIRST_SIGHT = "first_sight"  # 第一眼见到ta的瞬间
    FUNNY_EATING = "funny_eating"  # 小狗吃东西之前滑稽的故事
    DEPARTURE_REACTION = "departure_reaction"  # 出门前小狗反应的故事
    PROTECTION = "protection"  # 小狗保护你的故事
    PROTECTED_BY_OWNER = "protected_by_owner"  # 你保护小狗的故事
    WONDERFUL_MOMENT = "wonderful_moment"  # 让你有从未有过的奇妙感受的瞬间

class PersonalityType(str, Enum):
    SENSITIVE = "sensitive"
    BITING = "biting"
    SILLY = "silly"

class EvolutionType(str, Enum):
    NPC_TRIGGER = "npc_trigger"
    COLLAR_GROWTH = "collar_growth"
    MASTER_APPEARANCE = "master_appearance"
    REBORN = "reborn"

# Pet schemas
class PetBase(BaseModel):
    name: str
    breed: Optional[str] = None
    sound: Optional[str] = None
    color: Optional[str] = None
    gait: Optional[str] = None
    favorite_food: Optional[str] = None
    departure_way: Optional[str] = None
    personality: Optional[str] = None
    food_reaction: Optional[str] = None
    likes_clothes: bool = False
    is_watchful: bool = False
    is_clingy: bool = False
    likes: Optional[str] = None
    fears: Optional[str] = None
    avatar_url: Optional[str] = None

class PetCreate(PetBase):
    pass

class PetUpdate(BaseModel):
    name: Optional[str] = None
    breed: Optional[str] = None
    sound: Optional[str] = None
    color: Optional[str] = None
    gait: Optional[str] = None
    favorite_food: Optional[str] = None
    departure_way: Optional[str] = None
    personality: Optional[str] = None
    food_reaction: Optional[str] = None
    likes_clothes: Optional[bool] = None
    is_watchful: Optional[bool] = None
    is_clingy: Optional[bool] = None
    likes: Optional[str] = None
    fears: Optional[str] = None
    avatar_url: Optional[str] = None

class PetResponse(PetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Memory schemas
class MemoryBase(BaseModel):
    memory_type: MemoryType
    title: Optional[str] = None
    content: str
    media_url: Optional[str] = None
    trigger_npc: bool = False
    collar_evolution: int = 0

class MemoryCreate(MemoryBase):
    pass

class MemoryUpdate(BaseModel):
    memory_type: Optional[MemoryType] = None
    title: Optional[str] = None
    content: Optional[str] = None
    media_url: Optional[str] = None
    trigger_npc: Optional[bool] = None
    collar_evolution: Optional[int] = None

class MemoryResponse(MemoryBase):
    id: int
    pet_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Meeting story schemas (相遇故事 - 记录与宠物相遇的故事)
class MeetingStoryBase(BaseModel):
    story: str

class MeetingStoryCreate(MeetingStoryBase):
    pass

class MeetingStoryResponse(MeetingStoryBase):
    id: int
    pet_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Virtual home item schemas
class VirtualHomeItemBase(BaseModel):
    item_type: str
    item_name: str
    description: Optional[str] = None
    growth_level: int = 1

class VirtualHomeItemCreate(VirtualHomeItemBase):
    memory_id: Optional[int] = None

class VirtualHomeItemResponse(VirtualHomeItemBase):
    id: int
    pet_id: int
    memory_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

# Evolution record schemas
class EvolutionRecordBase(BaseModel):
    evolution_type: EvolutionType
    description: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

class EvolutionRecordCreate(EvolutionRecordBase):
    triggered_by_memory_id: Optional[int] = None

class EvolutionRecordResponse(EvolutionRecordBase):
    id: int
    pet_id: int
    triggered_by_memory_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

# Full pet profile with all related data (综合档案)
class FullPetProfileResponse(BaseModel):
    pet: PetResponse
    memories: List[MemoryResponse] = []
    meeting_story: Optional[MeetingStoryResponse] = None
    virtual_home_items: List[VirtualHomeItemResponse] = []
    evolution_records: List[EvolutionRecordResponse] = []
    emotional_profile: Optional["PetEmotionalProfileResponse"] = None
    recent_chats: List["ChatMessageResponse"] = []

# Image upload schemas
class ImageUploadResponse(BaseModel):
    url: str
    filename: str

# Dog identification schemas
class DogIdentificationResponse(BaseModel):
    breed: Optional[str] = None
    breed_confidence: Optional[float] = None
    color: Optional[str] = None
    life_stage: Optional[str] = None  # 幼年/成年/老年
    description: Optional[str] = None
    success: bool
    message: Optional[str] = None

# Extended pet profile schemas (emotional dimensions - 情感档案)
class PetEmotionalProfileBase(BaseModel):
    hardest_moment: Optional[str] = None          # TA离开后最难过的事
    regret: Optional[str] = None                   # 遗憾
    fear_of_forgetting: Optional[str] = None      # 最怕忘记TA什么
    wish_for_memorial_world: Optional[str] = None # 对记忆世界的愿望
    memory_to_preserve: Optional[str] = None      # 最想保存的记忆
    memorial_way: Optional[str] = None            # 纪念方式

class PetEmotionalProfileCreate(PetEmotionalProfileBase):
    pass

class PetEmotionalProfileResponse(PetEmotionalProfileBase):
    id: int
    pet_id: int
    extra_data: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Chat message schemas
class ChatMessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|pet)$")
    content: str

class ChatMessageResponse(BaseModel):
    id: int
    pet_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[ChatMessageResponse]] = None

class GenerateBeatRequest(BaseModel):
    previous_beat: Optional[str] = None

# Pet animation state schemas (2D世界宠物状态)
class PetStateUpdate(BaseModel):
    pos_x: Optional[float] = None           # X坐标
    pos_y: Optional[float] = None           # Y坐标
    pos_z: Optional[float] = None           # Z坐标
    current_animation: Optional[str] = None  # 动画状态
    is_moving: Optional[bool] = None         # 是否移动中
    target_x: Optional[float] = None        # 目标X
    target_y: Optional[float] = None        # 目标Y
    target_z: Optional[float] = None        # 目标Z
    move_speed: Optional[float] = None      # 移动速度
    facing_direction: Optional[str] = None  # 朝向

class PetStateResponse(BaseModel):
    id: int
    pet_id: int
    pos_x: float
    pos_y: float
    pos_z: float
    current_animation: str
    is_moving: bool
    target_x: Optional[float]
    target_y: Optional[float]
    target_z: Optional[float]
    move_speed: float
    facing_direction: str
    extra_data: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MoveCommand(BaseModel):
    target_x: float
    target_y: float
    target_z: Optional[float] = None
    move_speed: Optional[float] = None

class AnimationCommand(BaseModel):
    animation: str  # idle, walk, run, sit, lie, sleep, eat, bark, tail_wag, look_around, run_around, poop

# Custom animation registry schemas
class CustomAnimationCreate(BaseModel):
    name: str                          # 动画唯一名称，如 "happy_jump"
    display_name: Optional[str] = None  # 显示名称
    description: Optional[str] = None   # 描述
    animation_url: Optional[str] = None # 动画资源URL
    sprite_sheet_url: Optional[str] = None  # 精灵图URL
    frame_count: int = 1               # 帧数
    frame_duration: int = 100         # 每帧持续时间(ms)
    loop_count: int = -1              # 循环次数，-1=无限循环
    category: str = "custom"           # 分类: idle, action, emotion, special

class CustomAnimationUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    animation_url: Optional[str] = None
    sprite_sheet_url: Optional[str] = None
    frame_count: Optional[int] = None
    frame_duration: Optional[int] = None
    loop_count: Optional[int] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class CustomAnimationResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str]
    description: Optional[str]
    animation_url: Optional[str]
    sprite_sheet_url: Optional[str]
    frame_count: int
    frame_duration: int
    loop_count: int
    category: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Update forward reference
FullPetProfileResponse.model_rebuild()

# Phase 1 场景 schemas
class SceneRecordBase(BaseModel):
    scene_type: str
    scene_name: str
    description: Optional[str] = None

class SceneRecordCreate(SceneRecordBase):
    pet_id: Optional[int] = None
    trigger_memory_id: Optional[int] = None

class SceneRecordResponse(SceneRecordBase):
    id: int
    pet_id: int
    trigger_memory_id: Optional[int]
    is_completed: bool
    completed_at: Optional[datetime]
    extra_data: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

# Phase 3 情感旅程 schemas
class JourneyRecordBase(BaseModel):
    journey_type: str
    title: str
    content: Optional[str] = None
    next_suggestion: Optional[str] = None

class JourneyRecordCreate(JourneyRecordBase):
    pet_id: Optional[int] = None
    based_on_memory_id: Optional[int] = None

class JourneyRecordResponse(JourneyRecordBase):
    id: int
    pet_id: int
    based_on_memory_id: Optional[int]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# 自然口述 schemas
class NarrationRecordBase(BaseModel):
    raw_text: str

class NarrationRecordCreate(NarrationRecordBase):
    pet_id: Optional[int] = None

class NarrationRecordResponse(NarrationRecordBase):
    id: int
    pet_id: int
    parsed_memory_type: Optional[str]
    parsed_title: Optional[str]
    parsed_content: Optional[str]
    generated_item_name: Optional[str]
    generated_item_type: Optional[str]
    ai_response: Optional[str]
    is_processed: bool
    created_at: datetime

    class Config:
        from_attributes = True

# AI口述处理结果
class NarrationProcessResponse(BaseModel):
    narration: NarrationRecordResponse
    created_memory: Optional[MemoryResponse] = None
    created_item: Optional[VirtualHomeItemResponse] = None
    ai_suggestion: str
