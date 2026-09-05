from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging, sys

from backend_app.database import get_db, dict_from_row
from backend_app.prompts.pet_chat import build_system_prompt
from backend_app.prompts.pet_beat import build_beat_prompt

# 全局调试日志配置
logger = logging.getLogger("backend_app.routes")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    # 第三方库（httpx, httpcore）日志级别调低，避免刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
from backend_app.schemas import (
    PetCreate, PetUpdate, PetResponse,
    MemoryCreate, MemoryUpdate, MemoryResponse,
    MeetingStoryCreate, MeetingStoryResponse,
    VirtualHomeItemCreate, VirtualHomeItemResponse,
    EvolutionRecordCreate, EvolutionRecordResponse,
    FullPetProfileResponse,
    PetEmotionalProfileCreate, PetEmotionalProfileResponse,
    ChatMessageCreate, ChatMessageResponse, ChatRequest,
    CorrectionRequest, CorrectionResponse,
    GenerateBeatRequest,
    PetStateUpdate, PetStateResponse, MoveCommand, AnimationCommand,
    CustomAnimationCreate, CustomAnimationUpdate, CustomAnimationResponse,
    SceneRecordResponse, SceneRecordCreate,
    JourneyRecordResponse, JourneyRecordCreate,
    NarrationRecordResponse, NarrationRecordCreate,
    RelationshipMaterialResponse, InferredTraitResponse, PuppylandSharedResponse,
    DailyLetterResponse, GenerateLetterRequest,
    GenerateDogImageRequest
)

router = APIRouter()

# ============ Helper Functions ============

def parse_llm_json_response(result_text: str) -> dict:
    """解析LLM返回的JSON响应，处理各种格式问题"""
    import json
    import re
    try:
        return json.loads(result_text)
    except json.JSONDecodeError:
        pass
    # 尝试提取JSON块（处理LLM返回的可能包含markdown代码块的情况）
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    # 最后尝试查找第一个{到最后一个}之间的内容
    first_brace = result_text.find('{')
    last_brace = result_text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return json.loads(result_text[first_brace:last_brace+1])
    raise ValueError(f"无法解析JSON: {result_text[:200]}")

# ============ Pet Routes ============

@router.post("/pets", response_model=PetResponse, tags=["Pets"])
def create_pet(pet: PetCreate):
    """Create a new pet profile"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO pets (name, breed, sound, color, gait, favorite_food,
                            departure_way, personality, food_reaction, likes_clothes,
                            is_watchful, is_clingy, likes, fears, avatar_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pet.name, pet.breed, pet.sound, pet.color, pet.gait,
              pet.favorite_food, pet.departure_way, pet.personality,
              pet.food_reaction, int(pet.likes_clothes), int(pet.is_watchful),
              int(pet.is_clingy), pet.likes, pet.fears, pet.avatar_url))
        pet_id = cursor.lastrowid
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets", response_model=List[PetResponse], tags=["Pets"])
def list_pets(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)):
    """List all pets with pagination"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pets ORDER BY created_at DESC LIMIT ? OFFSET ?",
                      (limit, skip))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.get("/pets/{pet_id}", response_model=PetResponse, tags=["Pets"])
def get_pet(pet_id: int):
    """Get a specific pet by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")
        return pet

@router.get("/pets/{pet_id}/profile", response_model=FullPetProfileResponse, tags=["Pets"])
def get_pet_profile(pet_id: int):
    """Get full pet profile with memories, adoption story, virtual home items, evolution records, emotional profile, and recent chats"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Get pet
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        # Get memories
        cursor.execute("SELECT * FROM memories WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        memories = [dict_from_row(row) for row in cursor.fetchall()]

        # Get meeting story
        cursor.execute("SELECT * FROM meeting_stories WHERE pet_id = ?", (pet_id,))
        meeting_row = cursor.fetchone()
        meeting_story = dict_from_row(meeting_row) if meeting_row else None

        # Get virtual home items
        cursor.execute("SELECT * FROM virtual_home_items WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        virtual_home_items = [dict_from_row(row) for row in cursor.fetchall()]

        # Get evolution records
        cursor.execute("SELECT * FROM evolution_records WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        evolution_records = [dict_from_row(row) for row in cursor.fetchall()]

        # Get emotional profile
        cursor.execute("SELECT * FROM pet_profiles WHERE pet_id = ?", (pet_id,))
        emotional_row = cursor.fetchone()
        emotional_profile = dict_from_row(emotional_row) if emotional_row else None

        # Get recent chats
        cursor.execute("SELECT * FROM chat_messages WHERE pet_id = ? ORDER BY created_at DESC LIMIT 10", (pet_id,))
        recent_chats = [dict_from_row(row) for row in cursor.fetchall()]
        recent_chats.reverse()

        return {
            "pet": pet,
            "memories": memories,
            "meeting_story": meeting_story,
            "virtual_home_items": virtual_home_items,
            "evolution_records": evolution_records,
            "emotional_profile": emotional_profile,
            "recent_chats": recent_chats
        }

@router.put("/pets/{pet_id}", response_model=PetResponse, tags=["Pets"])
def update_pet(pet_id: int, pet_update: PetUpdate):
    """Update a pet's information"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if pet exists
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        # Build update query dynamically
        update_fields = []
        values = []
        for field, value in pet_update.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                if field in ['likes_clothes', 'is_watchful', 'is_clingy']:
                    values.append(int(value))
                else:
                    values.append(value)

        if update_fields:
            values.append(pet_id)
            cursor.execute(f"UPDATE pets SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                         values)

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        return dict_from_row(cursor.fetchone())

@router.delete("/pets/{pet_id}", tags=["Pets"])
def delete_pet(pet_id: int):
    """Delete a pet and all related data"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("DELETE FROM pets WHERE id = ?", (pet_id,))
        return {"message": "Pet deleted successfully"}

# ============ Memory Routes ============

@router.post("/pets/{pet_id}/memories", response_model=MemoryResponse, tags=["Memories"])
def create_memory(pet_id: int, memory: MemoryCreate):
    """Create a new memory for a pet"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if pet exists
        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            INSERT INTO memories (pet_id, memory_type, title, content, media_url, trigger_npc, collar_evolution)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pet_id, memory.memory_type.value, memory.title, memory.content,
              memory.media_url, int(memory.trigger_npc), memory.collar_evolution))
        memory_id = cursor.lastrowid

        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/memories", response_model=List[MemoryResponse], tags=["Memories"])
def list_memories(pet_id: int, memory_type: Optional[str] = None):
    """List all memories for a pet, optionally filtered by type"""
    with get_db() as conn:
        cursor = conn.cursor()
        if memory_type:
            cursor.execute("SELECT * FROM memories WHERE pet_id = ? AND memory_type = ? ORDER BY created_at DESC",
                         (pet_id, memory_type))
        else:
            cursor.execute("SELECT * FROM memories WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.get("/memories/{memory_id}", response_model=MemoryResponse, tags=["Memories"])
def get_memory(memory_id: int):
    """Get a specific memory by ID"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        memory = dict_from_row(cursor.fetchone())
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")
        return memory

@router.put("/memories/{memory_id}", response_model=MemoryResponse, tags=["Memories"])
def update_memory(memory_id: int, memory_update: MemoryUpdate):
    """Update a memory"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Memory not found")

        update_fields = []
        values = []
        for field, value in memory_update.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                if field == 'memory_type':
                    values.append(value.value)
                elif field in ['trigger_npc', 'collar_evolution']:
                    values.append(int(value))
                else:
                    values.append(value)

        if update_fields:
            values.append(memory_id)
            cursor.execute(f"UPDATE memories SET {', '.join(update_fields)} WHERE id = ?", values)

        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        return dict_from_row(cursor.fetchone())

@router.delete("/memories/{memory_id}", tags=["Memories"])
def delete_memory(memory_id: int):
    """Delete a memory"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Memory not found")
        cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        return {"message": "Memory deleted successfully"}

# ============ Meeting Story Routes ============

@router.post("/pets/{pet_id}/meeting-story", response_model=MeetingStoryResponse, tags=["Meeting"])
def create_meeting_story(pet_id: int, story: MeetingStoryCreate):
    """Create or update meeting story for a pet"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Check if pet exists
        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        # Check if meeting story already exists
        cursor.execute("SELECT id FROM meeting_stories WHERE pet_id = ?", (pet_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("UPDATE meeting_stories SET story = ? WHERE pet_id = ?",
                         (story.story, pet_id))
            story_id = existing[0]
        else:
            cursor.execute("INSERT INTO meeting_stories (pet_id, story) VALUES (?, ?)",
                         (pet_id, story.story))
            story_id = cursor.lastrowid

        cursor.execute("SELECT * FROM meeting_stories WHERE id = ?", (story_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/meeting-story", response_model=MeetingStoryResponse, tags=["Meeting"])
def get_meeting_story(pet_id: int):
    """Get meeting story for a pet"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM meeting_stories WHERE pet_id = ?", (pet_id,))
        story = dict_from_row(cursor.fetchone())
        if not story:
            raise HTTPException(status_code=404, detail="Meeting story not found")
        return story

# ============ Virtual Home Item Routes ============

@router.post("/pets/{pet_id}/virtual-items", response_model=VirtualHomeItemResponse, tags=["VirtualHome"])
def create_virtual_item(pet_id: int, item: VirtualHomeItemCreate):
    """Create a virtual home item from a memory"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            INSERT INTO virtual_home_items (pet_id, item_type, item_name, description, memory_id, growth_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pet_id, item.item_type, item.item_name, item.description,
              item.memory_id, item.growth_level))
        item_id = cursor.lastrowid

        cursor.execute("SELECT * FROM virtual_home_items WHERE id = ?", (item_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/virtual-items", response_model=List[VirtualHomeItemResponse], tags=["VirtualHome"])
def list_virtual_items(pet_id: int, item_type: Optional[str] = None):
    """List all virtual home items for a pet"""
    with get_db() as conn:
        cursor = conn.cursor()
        if item_type:
            cursor.execute("SELECT * FROM virtual_home_items WHERE pet_id = ? AND item_type = ? ORDER BY created_at DESC",
                         (pet_id, item_type))
        else:
            cursor.execute("SELECT * FROM virtual_home_items WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.put("/virtual-items/{item_id}/growth", response_model=VirtualHomeItemResponse, tags=["VirtualHome"])
def grow_virtual_item(item_id: int, growth_level: Optional[int] = Query(None, ge=1, le=10)):
    """Increase growth level of a virtual home item. If growth_level is not provided, increments by 1."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM virtual_home_items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Item not found")

        current_level = row['growth_level']
        if growth_level is None:
            new_level = min(current_level + 1, 10)
        else:
            new_level = growth_level

        cursor.execute("UPDATE virtual_home_items SET growth_level = ? WHERE id = ?",
                     (new_level, item_id))
        cursor.execute("SELECT * FROM virtual_home_items WHERE id = ?", (item_id,))
        return dict_from_row(cursor.fetchone())

# ============ Evolution Routes ============

@router.post("/pets/{pet_id}/evolutions", response_model=EvolutionRecordResponse, tags=["Evolution"])
def create_evolution(pet_id: int, evolution: EvolutionRecordCreate):
    """Record a pet's evolution/metamorphosis event"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            INSERT INTO evolution_records (pet_id, evolution_type, description, previous_state, new_state, triggered_by_memory_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pet_id, evolution.evolution_type.value, evolution.description,
              evolution.previous_state, evolution.new_state, evolution.triggered_by_memory_id))
        evolution_id = cursor.lastrowid

        cursor.execute("SELECT * FROM evolution_records WHERE id = ?", (evolution_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/evolutions", response_model=List[EvolutionRecordResponse], tags=["Evolution"])
def list_evolutions(pet_id: int, evolution_type: Optional[str] = None):
    """List all evolution records for a pet"""
    with get_db() as conn:
        cursor = conn.cursor()
        if evolution_type:
            cursor.execute("""
                SELECT * FROM evolution_records WHERE pet_id = ? AND evolution_type = ?
                ORDER BY created_at DESC
            """, (pet_id, evolution_type))
        else:
            cursor.execute("SELECT * FROM evolution_records WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

# ============ AI Generation Routes ============

@router.post("/pets/{pet_id}/generate-home-item", tags=["AI"])
def generate_home_item(pet_id: int, memory_id: int):
    """
    AI生成：根据记忆生成虚拟家园物品
    使用AI分析记忆内容，生成适合的虚拟家园物品
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get pet and memory info
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("SELECT * FROM memories WHERE id = ? AND pet_id = ?", (memory_id, pet_id))
        memory = dict_from_row(cursor.fetchone())
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")

        # 物品类型映射
        item_type_map = {
            "first_sight": ("photo", "📷"),
            "funny_eating": ("food", "🍖"),
            "departure_reaction": ("toy", "🧸"),
            "protection": ("medal", "🏅"),
            "protected_by_owner": ("heart", "💝"),
            "wonderful_moment": ("star", "⭐")
        }

        memory_type = memory.get('memory_type', 'default')
        item_type, icon = item_type_map.get(memory_type, ("default", "🎁"))

        # 尝试使用AI生成更具体的物品名称和描述
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "Qwen/Qwen3.6-27B"),
                        "messages": [{
                            "role": "user",
                            "content": f"""根据以下宠物记忆，生成一个适合放在虚拟家园中的物品名称和描述。

宠物名字：{pet.get('name', 'ta')}
记忆类型：{memory_type}
记忆内容：{memory.get('content', '')}

请用JSON格式返回：
{{
    "item_name": "物品名称（中文，5字以内）",
    "description": "物品描述（10字以内）",
    "item_type": "物品类型（toy/food/photo/medal/heart/star/default之一）"
}}

只返回JSON，不要其他内容。"""
                        }],
                        "temperature": 0.3
                    }
                )
                response.raise_for_status()
                result = response.json()
                result_text = result["choices"][0]["message"]["content"]

            result = parse_llm_json_response(result_text)
            suggested_item = {
                "item_type": result.get("item_type", item_type),
                "item_name": result.get("item_name", f"{pet.get('name', 'ta')}的纪念物"),
                "description": result.get("description", f"来自记忆：{memory.get('title', memory_type)}"),
                "growth_level": 1
            }

        except Exception as e:
            # 回退到基于记忆类型的默认物品
            suggested_item = {
                "item_type": item_type,
                "item_name": f"{icon} {pet.get('name', 'ta')}的纪念物",
                "description": f"来自记忆：{memory.get('title', memory_type)}",
                "growth_level": 1
            }

        return {
            "message": "AI生成完成",
            "pet_id": pet_id,
            "memory_id": memory_id,
            "suggested_item": suggested_item
        }

@router.post("/evolve/{pet_id}", tags=["AI"])
def trigger_evolution(pet_id: int, evolution_type: str):
    """
    AI触发宠物进化
    根据进化类型触发宠物的形态变化
    - npc_trigger: NPC触发，长出项圈
    - collar_growth: 项圈成长
    - master_appearance: 长出主人
    - reborn: 变成小狗的过程
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        # 这里可以接入AI服务来确定进化状态
        evolution_map = {
            "npc_trigger": {"previous": "沉睡", "new": "觉醒", "description": "NPC触发，宠物开始感知到主人的存在"},
            "collar_growth": {"previous": "无", "new": "项圈显现", "description": "象征羁绊的项圈开始显现"},
            "master_appearance": {"previous": "虚影", "new": "主人形态", "description": "主人的身影开始清晰"},
            "reborn": {"previous": "旧世界", "new": "新世界", "description": "带着记忆来到新的世界，开始新的生活"}
        }

        evolution_info = evolution_map.get(evolution_type, {})
        return {
            "message": "Evolution triggered",
            "pet_id": pet_id,
            "evolution_type": evolution_type,
            "previous_state": evolution_info.get("previous"),
            "new_state": evolution_info.get("new"),
            "description": evolution_info.get("description")
        }

# ============ Image Upload Routes ============

import os
import uuid
import httpx
from fastapi import UploadFile, File
from backend_app.schemas import ImageUploadResponse, DogIdentificationResponse

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-image", response_model=ImageUploadResponse, tags=["Image"])
async def upload_image(file: UploadFile = File(...)):
    """
    上传图片文件
    返回图片的URL地址
    """
    # 生成唯一文件名
    ext = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # 保存文件
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # 返回URL（实际项目中需要配置CDN或OSS）
    return ImageUploadResponse(
        url=f"/uploads/{filename}",
        filename=filename
    )

@router.post("/identify-dog", response_model=DogIdentificationResponse, tags=["AI"])
async def identify_dog(
    image_url: Optional[str] = Query(default=None, description="图片URL地址（公网可访问）"),
    file: Optional[UploadFile] = File(default=None, description="直接上传图片文件（支持 base64）")
):
    """
    使用AI识别图片中的狗狗信息
    返回品种、毛色、生命阶段等

    支持两种方式：
    1. image_url: 公网可访问的图片URL
    2. file: 直接上传图片文件
    """
    try:
        from dotenv import load_dotenv
        import base64

        load_dotenv(override=True)

        # 获取图片数据
        image_content = None
        if file:
            # 直接从上传文件读取并转为 base64
            contents = await file.read()
            image_content = base64.b64encode(contents).decode("utf-8")
        elif image_url:
            image_content = image_url
        else:
            return DogIdentificationResponse(
                success=False,
                message="请提供 image_url 或上传 file"
            )

        # 构建图片内容
        if file:
            # base64 上传
            image_data = f"data:{file.content_type or 'image/jpeg'};base64,{image_content}"
        else:
            # URL 方式
            image_data = image_url

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                os.getenv("base_url") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('api_key')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.getenv("model", "Qwen/Qwen3.6-27B"),
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": image_data}
                                },
                                {
                                    "type": "text",
                                    "text": """请仔细分析这张图片中的狗狗，用JSON格式返回以下信息：
{
    "breed": "狗的品种",
    "breed_confidence": 0.95,  // 置信度 0-1
    "color": "主要毛色",
    "life_stage": "幼年/成年/老年",
    "description": "简单描述一下这只狗的特征"
}
如果没有看到狗，返回 success: false。"""
                                }
                            ]
                        }
                    ],
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            result = response.json()
            result_text = result["choices"][0]["message"]["content"]

        # 尝试解析JSON
        try:
            result = parse_llm_json_response(result_text)
            return DogIdentificationResponse(
                breed=result.get("breed"),
                breed_confidence=result.get("breed_confidence"),
                color=result.get("color"),
                life_stage=result.get("life_stage"),
                description=result.get("description"),
                success=True
            )
        except Exception:
            return DogIdentificationResponse(
                success=False,
                message="无法解析识别结果"
            )

    except Exception as e:
        return DogIdentificationResponse(
            success=False,
            message=f"识别失败: {str(e)}"
        )

# ============ Extended Pet Profile Routes ============

@router.post("/pets/{pet_id}/emotional-profile", response_model=PetEmotionalProfileResponse, tags=["PetProfile"])
def create_or_update_pet_profile(pet_id: int, profile: PetEmotionalProfileCreate):
    """创建或更新宠物扩展档案（情感维度）"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        # 检查是否已存在
        cursor.execute("SELECT id FROM pet_profiles WHERE pet_id = ?", (pet_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE pet_profiles SET
                    hardest_moment = ?, regret = ?, fear_of_forgetting = ?,
                    wish_for_memorial_world = ?, memory_to_preserve = ?, memorial_way = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE pet_id = ?
            """, (profile.hardest_moment, profile.regret, profile.fear_of_forgetting,
                  profile.wish_for_memorial_world, profile.memory_to_preserve,
                  profile.memorial_way, pet_id))
            profile_id = existing[0]
        else:
            cursor.execute("""
                INSERT INTO pet_profiles (pet_id, hardest_moment, regret, fear_of_forgetting,
                    wish_for_memorial_world, memory_to_preserve, memorial_way)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pet_id, profile.hardest_moment, profile.regret, profile.fear_of_forgetting,
                  profile.wish_for_memorial_world, profile.memory_to_preserve, profile.memorial_way))
            profile_id = cursor.lastrowid

        cursor.execute("SELECT * FROM pet_profiles WHERE id = ?", (profile_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/emotional-profile", response_model=PetEmotionalProfileResponse, tags=["PetProfile"])
def get_pet_profile_emotional(pet_id: int):
    """获取宠物情感档案"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("SELECT * FROM pet_profiles WHERE pet_id = ?", (pet_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Emotional profile not found")
        return dict_from_row(row)

# ============ Chat Routes ============

@router.post("/pets/{pet_id}/chat", response_model=ChatMessageResponse, tags=["Chat"])
def send_message_to_pet(pet_id: int, chat_request: ChatRequest):
    """
    发送消息给宠物，AI会模拟宠物回复
    基于宠物档案和记忆生成个性化回复

    对话风格参考：
    - 极度简短（10-30字）
    - 纯真、狗狗视角、第一人称
    - 动作+对白混合
    - 不说"我记得以前"，只在当下陪伴
    - 不将新故事伪装成历史事实
    """
    # 敏感词检测（不进叙事，只做温和陪伴）
    SENSITIVE_PATTERNS = [
        '走了', '离开', '去世', '最后', '生病', '治疗', '安乐',
        '遗憾', '对不起', '后悔', '骨灰', '天堂', '彩虹桥',
        '受不了', '撑不住', '活不下去', '不想活'
    ]
    DISTRESS_PATTERNS = [
        '崩溃', '哭', '没有意义', '喘不过气', '难受死'
    ]

    def contains_pattern(text, patterns):
        return any(p in text for p in patterns)

    with get_db() as conn:
        cursor = conn.cursor()

        # 获取宠物信息
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        # 保存用户消息
        cursor.execute("""
            INSERT INTO chat_messages (pet_id, role, content) VALUES (?, 'user', ?)
        """, (pet_id, chat_request.message))
        user_msg_id = cursor.lastrowid

        # 获取历史消息（最近的10条）
        cursor.execute("""
            SELECT * FROM chat_messages WHERE pet_id = ? ORDER BY created_at DESC LIMIT 10
        """, (pet_id,))
        history = [dict_from_row(row) for row in cursor.fetchall()]
        history.reverse()

        # 获取安全记忆（grounding用）：按memory_type优先级 + 时间倒序
        # priority: first_sight(3) > wonderful_moment(2) > funny_eating(1) > others(0)
        cursor.execute("""
            SELECT * FROM memories WHERE pet_id = ? ORDER BY
                CASE memory_type
                    WHEN 'first_sight' THEN 3
                    WHEN 'wonderful_moment' THEN 2
                    WHEN 'funny_eating' THEN 1
                    ELSE 0
                END DESC,
                created_at DESC LIMIT 5
        """, (pet_id,))
        raw_memories = [dict_from_row(row) for row in cursor.fetchall()]

        # 过滤敏感记忆（涉及离别、遗憾等的不进入叙事 grounding）
        safe_memories = []
        for m in raw_memories:
            content = m.get('content', '')
            # 检查是否包含敏感词
            is_sensitive = contains_pattern(content, SENSITIVE_PATTERNS)
            if not is_sensitive:
                safe_memories.append(m)

        # 获取相遇故事
        cursor.execute("SELECT * FROM meeting_stories WHERE pet_id = ?", (pet_id,))
        meeting_row = cursor.fetchone()
        meeting_story = dict_from_row(meeting_row) if meeting_row else None

        # 获取情感档案
        cursor.execute("SELECT * FROM pet_profiles WHERE pet_id = ?", (pet_id,))
        profile_row = cursor.fetchone()
        emotional_profile = dict_from_row(profile_row) if profile_row else None

        # 构建角色设定（CharacterProfile）
        pet_name = pet.get('name') or 'TA'
        breed = pet.get('breed') or '不明'
        personality = pet.get('personality') or '温柔忠诚'
        likes = pet.get('likes') or '陪伴主人'
        fears = pet.get('fears') or '离开主人'

        # 查询关系素材（从数据库获取）
        cursor.execute("""
            SELECT material_type, content FROM relationship_materials
            WHERE pet_id = ? AND is_active = 1
            ORDER BY confidence DESC, created_at DESC
        """, (pet_id,))
        rel_materials_rows = cursor.fetchall()
        fixed_actions = []
        owner_phrases = []
        habits = []
        for row in rel_materials_rows:
            if row[0] == 'fixed_action':
                fixed_actions.append(row[1])
            elif row[0] == 'owner_phrase':
                owner_phrases.append(row[1])
            elif row[0] == 'habit':
                habits.append(row[1])

        # 查询推断的性格特征
        cursor.execute("""
            SELECT trait FROM inferred_traits
            WHERE pet_id = ? ORDER BY confidence DESC, created_at DESC
        """, (pet_id,))
        inferred_traits_rows = cursor.fetchall()
        inferred_traits = [row[0] for row in inferred_traits_rows]

        # 从记忆中提取关键物件和习惯
        key_objects = []
        key_habits = []
        precious_memory = ''

        for m in safe_memories[:3]:
            content = m.get('content', '')
            memory_type = m.get('memory_type', '')
            # 提取关键物件
            if any(k in content for k in ['球', '玩具', '骨头', '零食']):
                key_objects.append('玩具')
            if any(k in content for k in ['窝', '毯子', '垫子', '床']):
                key_objects.append('窝')
            if any(k in content for k in ['窗台', '窗户', '阳光']):
                key_objects.append('窗台')
            if any(k in content for k in ['门口', '钥匙', '回家']):
                key_objects.append('门口')
            if any(k in content for k in ['饭盆', '吃', '狗粮']):
                key_objects.append('饭盆')
            # 提取习惯
            if memory_type == 'funny_eating':
                key_habits.append(content[:30] if len(content) > 30 else content)
            if memory_type == 'wonderful_moment' and not precious_memory:
                precious_memory = content[:50]

        # 去重
        key_objects = list(dict.fromkeys(key_objects))[:4]
        key_habits = list(dict.fromkeys(key_habits))[:3]

        # 构建关系素材上下文
        traits_context = ""
        if inferred_traits:
            traits_context = "、".join(inferred_traits[:5])

        fixed_actions_context = ""
        if fixed_actions:
            fixed_actions_context = "\n".join([f"- {a}" for a in fixed_actions[:3]])

        owner_phrases_context = ""
        if owner_phrases:
            owner_phrases_context = "\n".join([f"- 主人常说：\"{p}\"" for p in owner_phrases[:2]])

        habits_context = ""
        if habits:
            habits_context = "\n".join([f"- {h}" for h in habits[:3]])

        # 构建纠正记录上下文
        corrections_context = ""
        cursor.execute("""
            SELECT * FROM corrections WHERE pet_id = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 10
        """, (pet_id,))
        corrections = [dict_from_row(row) for row in cursor.fetchall()]
        if corrections:
            correction_lines = []
            for c in corrections:
                correction_lines.append(f"- 以前{pet_name}会{c['original_behavior']}，但主人纠正说：{c['correction_text']}")
            corrections_context = "\n".join(correction_lines)
            logger.debug(f"[chat] corrections_context: {corrections_context[:100]}")

        # 构建记忆上下文
        memory_context = ""
        if safe_memories:
            memory_lines = []
            for m in safe_memories[:3]:
                mem_type_map = {
                    'first_sight': '第一次见面',
                    'funny_eating': '吃饭习惯',
                    'departure_reaction': '出门反应',
                    'protection': '保护主人',
                    'protected_by_owner': '被保护',
                    'wonderful_moment': '温暖时刻'
                }
                mem_type = mem_type_map.get(m.get('memory_type', ''), '记忆')
                memory_lines.append(f"- {mem_type}：{m.get('content', '')[:60]}")
            memory_context = "\n".join(memory_lines)

        system_prompt = build_system_prompt(
            pet_name=pet_name,
            breed=breed,
            traits_context=traits_context,
            likes=likes,
            fears=fears,
            fixed_actions_context=fixed_actions_context,
            owner_phrases_context=owner_phrases_context,
            habits_context=habits_context,
            memory_context=memory_context,
            corrections_context=corrections_context,
        )

        # 构建对话历史
        messages = [{"role": "system", "content": system_prompt}]
        for h in history:
            role = "assistant" if h["role"] == "pet" else h["role"]
            messages.append({"role": role, "content": h["content"]})
        messages.append({"role": "user", "content": chat_request.message})

        # 检测用户消息情绪
        user_msg = chat_request.message
        is_distress = contains_pattern(user_msg, DISTRESS_PATTERNS)
        is_sensitive = contains_pattern(user_msg, SENSITIVE_PATTERNS)
        logger.debug(f"[chat] pet_id={pet_id} user_msg='{user_msg[:50]}' is_distress={is_distress} is_sensitive={is_sensitive} history_len={len(history)}")

        # 调用AI生成回复
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            model = os.getenv("model", "Qwen/Qwen3.6-27B")
            logger.info(f"[chat] >>> Calling LLM API (model={model}) for pet_id={pet_id}")
            # 打印完整消息列表内容，方便调试
            history_msgs = [f"[{m['role']}] {m['content'][:60]}" for m in messages[1:]]
            logger.debug(f"[chat] messages to LLM: system_prompt({len(messages[0]['content'])} chars) + history({len(history_msgs)} msgs): {history_msgs} | current_user: '{user_msg[:80]}'")

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.5,
                        "max_tokens": 300
                    }
                )
                response.raise_for_status()
                result = response.json()
                pet_reply = result["choices"][0]["message"]["content"]

            logger.info(f"[chat] <<< LLM response received ({len(pet_reply)} chars) pet_id={pet_id}: '{pet_reply[:80]}'")

            # 清理回复：移除多余的空行和冗余格式
            pet_reply = pet_reply.strip()

            # 尝试解析 JSON 格式 {act, say}，兼容旧纯文本格式
            import json
            pet_act = None
            pet_say = pet_reply
            try:
                parsed = json.loads(pet_reply)
                if isinstance(parsed, dict) and "act" in parsed and "say" in parsed:
                    pet_act = parsed.get("act", "") or ""
                    pet_say = parsed.get("say", "") or pet_reply
                    logger.debug(f"[chat] JSON parsed: act='{pet_act}' say='{pet_say}'")
                else:
                    logger.debug(f"[chat] JSON but missing act/say fields, treating as plain text: '{pet_reply[:60]}'")
            except Exception:
                logger.debug(f"[chat] Not JSON, treating as plain text reply: '{pet_reply[:60]}'")

        except Exception as e:
            # 回退回复（网络错误时）
            logger.warning(f"[chat] !!! LLM API failed for pet_id={pet_id}: {e}")
            if is_distress or is_sensitive:
                pet_say = "过来靠在主人身边，安静地陪着主人。\n不用说什么，我在这里。"
                pet_act = "安静地靠在主人身边"
                logger.info(f"[chat] --- Using distress fallback reply (pet_id={pet_id})")
            else:
                fallback_replies = [
                    ("尾巴轻轻摇了摇。\n嗯，我听着呢。", "尾巴轻轻摇了一下"),
                    ("歪了歪头，看主人。\n我在呢。", "歪头看着主人"),
                    ("蹭了蹭主人的腿。\n一直都在。", "蹭了蹭主人的腿"),
                    ("趴在主人脚边，尾巴慢慢扫过地面。\n陪你。", "趴在主人脚边"),
                ]
                import random
                chosen = random.choice(fallback_replies)
                pet_say = chosen[0]
                pet_act = chosen[1]
                logger.info(f"[chat] --- Using random fallback reply (pet_id={pet_id}): '{pet_say[:60]}'")

        # 保存宠物回复（act 仅 pet 消息有值）
        cursor.execute("""
            INSERT INTO chat_messages (pet_id, role, content, act) VALUES (?, 'pet', ?, ?)
        """, (pet_id, pet_say, pet_act))
        pet_msg_id = cursor.lastrowid

        cursor.execute("SELECT * FROM chat_messages WHERE id = ?", (pet_msg_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/chat", response_model=List[ChatMessageResponse], tags=["Chat"])
def get_chat_history(pet_id: int, limit: int = Query(50, ge=1, le=100)):
    """获取与宠物的聊天记录"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            SELECT * FROM chat_messages WHERE id IN (
                SELECT MAX(id) FROM chat_messages WHERE pet_id = ? GROUP BY role, content
            ) ORDER BY created_at DESC LIMIT ?
        """, (pet_id, limit))
        messages = [dict_from_row(row) for row in cursor.fetchall()]
        messages.reverse()
        return messages

@router.post("/pets/{pet_id}/corrections", response_model=CorrectionResponse, tags=["Chat"])
def save_correction(pet_id: int, request: CorrectionRequest):
    """
    保存主人对宠物行为的纠正记录。
    纠正内容会进入宠物的行为记忆，后续对话生成时会参考此信息。
    """
    from backend_app.schemas import CorrectionRequest, CorrectionResponse
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")
        cursor.execute("""
            INSERT INTO corrections (pet_id, original_behavior, correction_text)
            VALUES (?, ?, ?)
        """, (pet_id, request.original_behavior, request.correction_text))
        correction_id = cursor.lastrowid
        logger.info(f"[correction] saved pet_id={pet_id}: '{request.original_behavior}' <- '{request.correction_text}'")
        cursor.execute("SELECT * FROM corrections WHERE id = ?", (correction_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/corrections", response_model=List[CorrectionResponse], tags=["Chat"])
def get_corrections(pet_id: int):
    """获取宠物所有纠正记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")
        cursor.execute("""
            SELECT * FROM corrections WHERE pet_id = ? ORDER BY created_at DESC
        """, (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.post("/pets/{pet_id}/generate-beat", tags=["AI"])
def generate_beat(pet_id: int, request: GenerateBeatRequest = None):
    """
    AI 根据宠物档案和记忆生成个性化剧情片段
    返回：环境描写、动作、对白、推进语、姿态
    """
    prev_env = request.previous_beat if request else None

    NIGHT_WORDS = ['暗', '夜', '灯', '黑', '黄昏', '傍晚', '暮']
    DAY_WORDS = ['阳光', '天亮', '白天', '午后', '早晨', '晨']

    def is_env_consistent(env):
        if not prev_env:
            # 没有前一幕可比对时，直接采信 LLM 自己生成的环境描写
            return True
        has_night = any(c in prev_env for c in NIGHT_WORDS)
        has_day = any(c in prev_env for c in DAY_WORDS)
        if has_night and not any(c in env for c in NIGHT_WORDS):
            return False
        if has_day and not any(c in env for c in DAY_WORDS):
            return False
        return True

    def generate_consistent_env(prev_env_text):
        if not prev_env_text:
            return "房间里安静而温暖，TA安静地趴在主人脚边。"
        is_night = any(c in prev_env_text for c in NIGHT_WORDS)
        is_day = any(c in prev_env_text for c in DAY_WORDS)
        if is_night:
            return "房间里只剩下一盏灯，暖黄的光洒在地板上，TA安静地趴在主人脚边。"
        elif is_day:
            return "阳光透过窗户洒进来，TA在光影里安静地趴着。"
        return prev_env_text

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            SELECT * FROM memories WHERE pet_id = ? ORDER BY
                CASE memory_type
                    WHEN 'first_sight' THEN 3
                    WHEN 'wonderful_moment' THEN 2
                    WHEN 'funny_eating' THEN 1
                    ELSE 0
                END DESC,
                created_at DESC LIMIT 3
        """, (pet_id,))
        raw_memories = [dict_from_row(row) for row in cursor.fetchall()]

        SENSITIVE = ['走了', '离开', '去世', '最后', '生病', '治疗', '安乐', '遗憾', '对不起', '后悔', '骨灰', '天堂', '彩虹桥']
        safe_memories = [m for m in raw_memories if not any(p in m.get('content', '') for p in SENSITIVE)]

        pet_name = pet.get('name') or 'TA'
        breed = pet.get('breed') or '不明'
        personality = pet.get('personality') or '温柔忠诚'
        likes = pet.get('likes') or '陪伴主人'
        fears = pet.get('fears') or '离开主人'

        # 查询关系素材
        cursor.execute("""
            SELECT material_type, content FROM relationship_materials
            WHERE pet_id = ? AND is_active = 1
            ORDER BY confidence DESC, created_at DESC
        """, (pet_id,))
        rel_materials_rows = cursor.fetchall()
        fixed_actions = []
        owner_phrases = []
        habits = []
        for row in rel_materials_rows:
            if row[0] == 'fixed_action':
                fixed_actions.append(row[1])
            elif row[0] == 'owner_phrase':
                owner_phrases.append(row[1])
            elif row[0] == 'habit':
                habits.append(row[1])

        # 查询推断的性格特征
        cursor.execute("""
            SELECT trait FROM inferred_traits
            WHERE pet_id = ? ORDER BY confidence DESC, created_at DESC
        """, (pet_id,))
        inferred_traits_rows = cursor.fetchall()
        inferred_traits = [row[0] for row in inferred_traits_rows]

        # 构建关系素材上下文
        traits_context = ""
        if inferred_traits:
            traits_context = "、".join(inferred_traits[:5])

        fixed_actions_context = ""
        if fixed_actions:
            fixed_actions_context = "\n".join([f"- {a}" for a in fixed_actions[:3]])

        habits_context = ""
        if habits:
            habits_context = "\n".join([f"- {h}" for h in habits[:3]])

        memory_context = ""
        if safe_memories:
            mem_type_map = {
                'first_sight': '第一次见面',
                'funny_eating': '吃饭习惯',
                'departure_reaction': '出门反应',
                'protection': '保护主人',
                'protected_by_owner': '被保护',
                'wonderful_moment': '温暖时刻'
            }
            memory_lines = []
            for m in safe_memories[:3]:
                mem_label = mem_type_map.get(m.get('memory_type', ''), '记忆')
                memory_lines.append("- " + mem_label + "：" + m.get('content', '')[:60])
            memory_context = "\n".join(memory_lines)

        prompt = build_beat_prompt(
            pet_name=pet_name,
            breed=breed,
            traits_context=traits_context,
            likes=likes,
            fears=fears,
            fixed_actions_context=fixed_actions_context,
            habits_context=habits_context,
            memory_context=memory_context,
        )

        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            import httpx
            model = os.getenv("model", "deepseek-v4-flash")
            logger.info(f"[beat] >>> Calling LLM API (model={model}) for pet_id={pet_id}")
            logger.debug(f"[beat] prompt length={len(prompt)} chars, prev_env='{prev_env}'")

            client = httpx.Client(timeout=120.0)
            response = client.post(
                os.getenv("base_url") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('api_key')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8,
                    "max_tokens": 200
                }
            )
            response.raise_for_status()
            result = response.json()
            raw = result["choices"][0]["message"]["content"].strip()
            logger.info(f"[beat] <<< LLM response received ({len(raw)} chars) pet_id={pet_id}: '{raw[:100]}'")

            import json, re
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            if match:
                json_str = match.group(1)
                logger.debug(f"[beat] Extracted JSON from code block (len={len(json_str)})")
            else:
                json_str = raw

            beat = json.loads(json_str)
            logger.debug(f"[beat] Parsed beat: env='{beat.get('env','')[:40]}' act='{beat.get('act','')[:40]}' say='{beat.get('say','')[:40]}' pose='{beat.get('pose','')}'")

            env = beat.get("env", "")
            if not is_env_consistent(env):
                logger.debug(f"[beat] env inconsistent, overriding with consistent env (prev_env='{prev_env}')")
                beat["env"] = generate_consistent_env(prev_env or "")

            allowed_pose = {"idle", "approach", "happy", "run", "down", "sleep"}
            if beat.get("pose") not in allowed_pose:
                logger.debug(f"[beat] invalid pose '{beat.get('pose')}', defaulting to 'idle'")
                beat["pose"] = "idle"

            return beat

        except Exception as e:
            import random
            logger.warning(f"[beat] !!! LLM API failed for pet_id={pet_id}: {e}")
            fallback_beats = [
                {"env": "房间里安静而温暖，TA安静地趴在主人脚边。", "act": pet_name + "轻轻摇着尾巴，耳朵微微动了一下。", "say": "我在这里陪你。", "push": "和" + pet_name + "安静地待着。", "pose": "idle"},
                {"env": "阳光透过窗户洒进来，TA在光影里安静地趴着。", "act": pet_name + "抬起头，看着主人，尾巴慢慢扫过地面。", "say": "你回来了。", "push": "和" + pet_name + "一起晒太阳。", "pose": "idle"},
                {"env": "房间里只剩下一盏灯，暖黄的光洒在地板上。", "act": pet_name + "蜷在你脚边，身体暖暖的。", "say": "今晚也在。", "push": "和" + pet_name + "一起入睡。", "pose": "sleep"},
            ]
            chosen = random.choice(fallback_beats)
            logger.info(f"[beat] --- Using fallback beat (pet_id={pet_id}): env='{chosen['env'][:40]}'")
            return chosen

# ============ Pet State Routes (2D Animation) ============

@router.post("/pets/{pet_id}/state", response_model=PetStateResponse, tags=["PetState"])
def create_or_update_pet_state(pet_id: int, state: PetStateUpdate):
    """
    创建或更新宠物状态（位置、动画等）
    如果宠物状态不存在则创建，存在则更新
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        # 检查是否已存在状态
        cursor.execute("SELECT id FROM pet_states WHERE pet_id = ?", (pet_id,))
        existing = cursor.fetchone()

        # 构建更新字段
        update_fields = []
        values = []
        for field, value in state.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                if field == 'is_moving':
                    values.append(int(value))
                else:
                    values.append(value)

        if existing:
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(pet_id)
                cursor.execute(f"UPDATE pet_states SET {', '.join(update_fields)} WHERE pet_id = ?", values)
            state_id = existing[0]
        else:
            # 创建新状态
            cursor.execute("""
                INSERT INTO pet_states (pet_id, pos_x, pos_y, pos_z, current_animation, is_moving, facing_direction)
                VALUES (?, ?, ?, ?, 'idle', 0, 'right')
            """, (pet_id, state.pos_x or 0, state.pos_y or 0, state.pos_z or 0))
            state_id = cursor.lastrowid
            # 如果有额外字段需要更新
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(state_id)
                cursor.execute(f"UPDATE pet_states SET {', '.join(update_fields)} WHERE id = ?", values)

        cursor.execute("SELECT * FROM pet_states WHERE id = ?", (state_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/state", response_model=PetStateResponse, tags=["PetState"])
def get_pet_state(pet_id: int):
    """获取宠物当前状态（位置、动画等）"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("SELECT * FROM pet_states WHERE pet_id = ?", (pet_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pet state not found")
        return dict_from_row(row)

@router.post("/pets/{pet_id}/move", response_model=PetStateResponse, tags=["PetState"])
def move_pet(pet_id: int, command: MoveCommand):
    """
    移动宠物到指定位置
    - 设置目标位置后，宠物开始移动
    - 前端通过轮询 /state 获取当前位置
    - 到达目标后 is_moving 变为 false
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("SELECT * FROM pet_states WHERE pet_id = ?", (pet_id,))
        row = cursor.fetchone()
        if not row:
            # 如果没有状态，先创建一个
            cursor.execute("""
                INSERT INTO pet_states (pet_id, pos_x, pos_y, pos_z, current_animation, is_moving, facing_direction)
                VALUES (?, 0, 0, 0, 'walk', 1, 'right')
            """, (pet_id,))
            state_id = cursor.lastrowid
        else:
            state_id = row['id']

        # 更新目标位置和移动状态
        target_z = command.target_z if command.target_z is not None else row['pos_z'] if row else 0
        move_speed = command.move_speed if command.move_speed is not None else row['move_speed'] if row else 100

        cursor.execute("""
            UPDATE pet_states SET
                target_x = ?, target_y = ?, target_z = ?,
                move_speed = ?, is_moving = 1, current_animation = 'walk',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (command.target_x, command.target_y, target_z, move_speed, state_id))

        cursor.execute("SELECT * FROM pet_states WHERE id = ?", (state_id,))
        return dict_from_row(cursor.fetchone())

@router.post("/pets/{pet_id}/stop", response_model=PetStateResponse, tags=["PetState"])
def stop_pet(pet_id: int):
    """
    停止宠物移动
    - 立即停止动画，切换到 idle 状态
    - 记录当前位置为目标位置
    - 用于前端发出"停止"指令时调用
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("SELECT * FROM pet_states WHERE pet_id = ?", (pet_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pet state not found")

        # 停止移动，当前位置作为新的基准点，清除目标
        cursor.execute("""
            UPDATE pet_states SET
                is_moving = 0,
                current_animation = 'idle',
                pos_x = COALESCE(target_x, pos_x),
                pos_y = COALESCE(target_y, pos_y),
                pos_z = COALESCE(target_z, pos_z),
                target_x = NULL,
                target_y = NULL,
                target_z = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE pet_id = ?
        """, (pet_id,))

        cursor.execute("SELECT * FROM pet_states WHERE pet_id = ?", (pet_id,))
        return dict_from_row(cursor.fetchone())

@router.post("/pets/{pet_id}/animation", response_model=PetStateResponse, tags=["PetState"])
def set_animation(pet_id: int, command: AnimationCommand):
    """
    设置宠物动画状态
    - idle: 站立待机
    - walk: 走路
    - run: 跑步
    - sit: 坐下
    - lie: 躺下
    - sleep: 睡觉
    - eat: 吃东西
    - bark: 吠叫
    - tail_wag: 摇尾巴
    - look_around: 环顾四周
    - run_around: 跑来跑去
    - poop: 便便
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("SELECT * FROM pet_states WHERE pet_id = ?", (pet_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO pet_states (pet_id, current_animation, is_moving, facing_direction)
                VALUES (?, 'idle', 0, 'right')
            """, (pet_id,))
            state_id = cursor.lastrowid
        else:
            state_id = row['id']

        cursor.execute("""
            UPDATE pet_states SET
                current_animation = ?,
                is_moving = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (command.animation, state_id))

        cursor.execute("SELECT * FROM pet_states WHERE id = ?", (state_id,))
        return dict_from_row(cursor.fetchone())

# ============ Custom Animation Routes ============

@router.post("/animations", response_model=CustomAnimationResponse, tags=["Animation"])
def create_custom_animation(animation: CustomAnimationCreate):
    """注册自定义动画"""
    with get_db() as conn:
        cursor = conn.cursor()

        # 检查是否已存在同名动画
        cursor.execute("SELECT id FROM custom_animations WHERE name = ?", (animation.name,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Animation '{animation.name}' already exists")

        cursor.execute("""
            INSERT INTO custom_animations (name, display_name, description, animation_url,
                sprite_sheet_url, frame_count, frame_duration, loop_count, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (animation.name, animation.display_name, animation.description,
              animation.animation_url, animation.sprite_sheet_url,
              animation.frame_count, animation.frame_duration, animation.loop_count, animation.category))
        anim_id = cursor.lastrowid

        cursor.execute("SELECT * FROM custom_animations WHERE id = ?", (anim_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/animations", response_model=List[CustomAnimationResponse], tags=["Animation"])
def list_animations(category: Optional[str] = None, is_active: Optional[bool] = None):
    """获取动画列表"""
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM custom_animations WHERE 1=1"
        params = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(int(is_active))

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.get("/animations/categories", tags=["Animation"])
def get_animation_categories():
    """获取所有动画分类"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM custom_animations ORDER BY category")
        categories = [row[0] for row in cursor.fetchall()]
        return {"categories": categories}

@router.get("/animations/{name}", response_model=CustomAnimationResponse, tags=["Animation"])
def get_animation_by_name(name: str):
    """通过名称获取动画"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_animations WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Animation '{name}' not found")
        return dict_from_row(row)

@router.put("/animations/{name}", response_model=CustomAnimationResponse, tags=["Animation"])
def update_animation(name: str, update: CustomAnimationUpdate):
    """更新动画信息"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM custom_animations WHERE name = ?", (name,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Animation '{name}' not found")

        update_fields = []
        values = []
        for field, value in update.model_dump(exclude_unset=True).items():
            if value is not None:
                update_fields.append(f"{field} = ?")
                if field == 'is_active':
                    values.append(int(value))
                else:
                    values.append(value)

        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(name)
            cursor.execute(f"UPDATE custom_animations SET {', '.join(update_fields)} WHERE name = ?", values)

        cursor.execute("SELECT * FROM custom_animations WHERE name = ?", (name,))
        return dict_from_row(cursor.fetchone())

@router.delete("/animations/{name}", tags=["Animation"])
def delete_animation(name: str):
    """删除动画"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM custom_animations WHERE name = ?", (name,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"Animation '{name}' not found")

        cursor.execute("DELETE FROM custom_animations WHERE name = ?", (name,))
        return {"message": f"Animation '{name}' deleted successfully"}

# ============ Phase 1 Scene Routes (三段第一阶段场景) ============

# 场景类型常量
SCENE_TYPES = {
    "first_meeting": {
        "name": "第一眼相遇",
        "description": "ta主动靠近你的那一刻",
        "icon": "👋"
    },
    "waiting_home": {
        "name": "等待回家",
        "description": "ta在门口等候你的样子",
        "icon": "🚪"
    },
    "dining_together": {
        "name": "一起吃饭",
        "description": "日常温馨的用餐时光",
        "icon": "🍽️"
    }
}

@router.get("/pets/{pet_id}/scenes", response_model=List[SceneRecordResponse], tags=["Phase1"])
def list_scenes(pet_id: int):
    """获取宠物的所有场景记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scene_records WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.get("/pets/{pet_id}/scenes/available", tags=["Phase1"])
def get_available_scenes(pet_id: int):
    """获取可触发的场景"""
    with get_db() as conn:
        cursor = conn.cursor()

        # 检查宠物是否存在
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        # 获取已完成的场景
        cursor.execute("SELECT scene_type FROM scene_records WHERE pet_id = ? AND is_completed = 1", (pet_id,))
        completed = {row[0] for row in cursor.fetchall()}

        # 获取宠物信息用于个性化
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())

        available = []
        for scene_type, info in SCENE_TYPES.items():
            if scene_type not in completed:
                available.append({
                    "scene_type": scene_type,
                    "scene_name": info["name"],
                    "description": info["description"].replace("ta", pet.get("name", "ta")),
                    "icon": info["icon"]
                })

        return {"available_scenes": available, "completed_count": len(completed)}

@router.post("/pets/{pet_id}/scenes", response_model=SceneRecordResponse, tags=["Phase1"])
def trigger_scene(pet_id: int, scene_type: str = Query(..., description="场景类型: first_meeting/waiting_home/dining_together")):
    """触发一个场景（Phase 1核心功能）"""
    with get_db() as conn:
        cursor = conn.cursor()

        # 检查宠物是否存在
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        # 验证场景类型
        if scene_type not in SCENE_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid scene_type. Must be one of: {list(SCENE_TYPES.keys())}")

        # 检查是否已完成
        cursor.execute("SELECT * FROM scene_records WHERE pet_id = ? AND scene_type = ? AND is_completed = 1", (pet_id, scene_type))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="This scene has already been completed")

        # 获取或创建场景记录
        cursor.execute("SELECT * FROM scene_records WHERE pet_id = ? AND scene_type = ?", (pet_id, scene_type))
        existing = cursor.fetchone()

        if existing:
            scene_id = existing[0]
        else:
            scene_info = SCENE_TYPES[scene_type]
            cursor.execute("""
                INSERT INTO scene_records (pet_id, scene_type, scene_name, description)
                VALUES (?, ?, ?, ?)
            """, (pet_id, scene_type, scene_info["name"], scene_info["description"]))
            scene_id = cursor.lastrowid

        cursor.execute("SELECT * FROM scene_records WHERE id = ?", (scene_id,))
        return dict_from_row(cursor.fetchone())

@router.put("/pets/{pet_id}/scenes/{scene_id}/complete", response_model=SceneRecordResponse, tags=["Phase1"])
def complete_scene(pet_id: int, scene_id: int, memory_id: int = Query(None, description="关联的记忆ID")):
    """完成一个场景，标记为已完成并关联记忆"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM scene_records WHERE id = ? AND pet_id = ?", (scene_id, pet_id))
        scene = dict_from_row(cursor.fetchone())
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        if scene["is_completed"]:
            raise HTTPException(status_code=400, detail="Scene already completed")

        cursor.execute("""
            UPDATE scene_records SET is_completed = 1, completed_at = CURRENT_TIMESTAMP, trigger_memory_id = ?
            WHERE id = ?
        """, (memory_id, scene_id))

        cursor.execute("SELECT * FROM scene_records WHERE id = ?", (scene_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/scenes/templates", tags=["Phase1"])
def get_scene_templates():
    """获取所有场景模板"""
    return [
        {"scene_type": k, "name": v["name"], "description": v["description"], "icon": v["icon"]}
        for k, v in SCENE_TYPES.items()
    ]

# ============ Phase 3 Journey Routes (情感旅程) ============

@router.get("/pets/{pet_id}/journeys", response_model=List[JourneyRecordResponse], tags=["Phase3"])
def list_journeys(pet_id: int, is_active: Optional[bool] = None):
    """获取宠物的情感旅程列表"""
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM journey_records WHERE pet_id = ?"
        params = [pet_id]
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(int(is_active))
        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.post("/pets/{pet_id}/journeys", response_model=JourneyRecordResponse, tags=["Phase3"])
def create_journey(pet_id: int, journey: JourneyRecordCreate):
    """创建新的情感旅程"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            INSERT INTO journey_records (pet_id, journey_type, title, content, based_on_memory_id, next_suggestion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pet_id, journey.journey_type, journey.title, journey.content,
              journey.based_on_memory_id, journey.next_suggestion))
        journey_id = cursor.lastrowid

        cursor.execute("SELECT * FROM journey_records WHERE id = ?", (journey_id,))
        return dict_from_row(cursor.fetchone())

@router.post("/pets/{pet_id}/journeys/generate", response_model=JourneyRecordResponse, tags=["Phase3"])
def generate_journey(pet_id: int):
    """
    AI生成情感旅程（Phase 3核心功能）
    基于宠物的记忆和档案，生成一段情感旅程
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # 获取宠物信息
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        # 获取记忆
        cursor.execute("SELECT * FROM memories WHERE pet_id = ? ORDER BY created_at DESC LIMIT 5", (pet_id,))
        memories = [dict_from_row(row) for row in cursor.fetchall()]

        # 获取情感档案
        cursor.execute("SELECT * FROM pet_profiles WHERE pet_id = ?", (pet_id,))
        profile = dict_from_row(cursor.fetchone())

        # 生成旅程
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            memories_text = "\n".join([f"- {m['memory_type']}: {m['content'][:100]}" for m in memories]) if memories else "暂无记忆"

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "Qwen/Qwen3.6-27B"),
                        "messages": [{
                            "role": "user",
                            "content": f"""基于以下宠物信息，生成一段情感旅程故事。

宠物名字：{pet.get('name', 'ta')}
性格：{pet.get('personality', '未知')}
最喜欢的回忆：{memories_text}
主人的遗憾：{profile.get('regret', '未知') if profile else '未知'}
主人的愿望：{profile.get('wish_for_memorial_world', '未知') if profile else '未知'}

请生成一段50字左右的情感旅程，格式为JSON：
{{
    "journey_type": "continuation",  // continuation/new_memory/legacy
    "title": "旅程标题（10字以内）",
    "content": "旅程内容（50字左右的故事）",
    "next_suggestion": "引导用户继续的下一句话"
}}

只返回JSON。"""
                        }],
                        "temperature": 0.7
                    }
                )
                response.raise_for_status()
                result = response.json()
                result_text = result["choices"][0]["message"]["content"]

            result = parse_llm_json_response(result_text)
            based_on_memory_id = memories[0]["id"] if memories else None
            cursor.execute("""
                INSERT INTO journey_records (pet_id, journey_type, title, content, based_on_memory_id, next_suggestion)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pet_id, result.get("journey_type", "continuation"), result.get("title", "新的旅程"),
                  result.get("content", ""), based_on_memory_id, result.get("next_suggestion", "")))
            journey_id = cursor.lastrowid
            cursor.execute("SELECT * FROM journey_records WHERE id = ?", (journey_id,))
            return dict_from_row(cursor.fetchone())

        except Exception as e:
            # 降级处理
            cursor.execute("""
                INSERT INTO journey_records (pet_id, journey_type, title, content, next_suggestion)
                VALUES (?, 'continuation', '新的旅程', '和ta一起，继续这段温暖的旅程', '想继续听下去吗？')
            """, (pet_id,))
            journey_id = cursor.lastrowid
            cursor.execute("SELECT * FROM journey_records WHERE id = ?", (journey_id,))
            return dict_from_row(cursor.fetchone())

# ============ Narration Routes (自然口述生长) ============

@router.post("/pets/{pet_id}/narrations", response_model=NarrationRecordResponse, tags=["Narration"])
def process_narration(pet_id: int, narration: NarrationRecordCreate):
    """
    处理用户自然口述（核心功能）
    AI解析用户描述，自动生成记忆和虚拟物品
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        raw_text = narration.raw_text

        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "Qwen/Qwen3.6-27B"),
                        "messages": [{
                            "role": "user",
                            "content": f"""分析用户关于宠物"{pet.get('name', 'ta')}"的描述，提取信息并生成记忆和物品。

用户描述：{raw_text}

请以JSON格式返回：
{{
    "parsed_memory_type": "first_sight/funny_eating/departure_reaction/protection/protected_by_owner/wonderful_moment",
    "parsed_title": "5字以内的标题",
    "parsed_content": "完整描述（20字以上）",
    "generated_item_name": "生成的物品名称",
    "generated_item_type": "toy/food/photo/medal/heart/star/default",
    "ai_response": "AI的温柔回应（20字以内）",
    "relationship_materials": {{
        "fixed_actions": ["具体的行为链描述，如'等主人放包脱鞋后才慢吞吞过来'，最多2个"],
        "owner_phrases": ["主人经常说的固定用语，如'想我就直说嘛'，最多2个"],
        "habits": ["习惯性行为，如'一听到钥匙声就冲过来'，最多2个"]
    }},
    "inferred_traits": ["从行为推断的性格，如'嘴硬'/'贪吃'/'胆小'，最多2个"],
    "provenance": "user_reported"
}}

只返回JSON。"""
                        }],
                        "temperature": 0.3
                    }
                )
                response.raise_for_status()
                result = response.json()
                result_text = result["choices"][0]["message"]["content"]

            import json
            import re
            # 尝试直接解析，如果失败则尝试提取JSON块
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # 尝试提取JSON块（处理LLM返回的可能包含markdown代码块的情况）
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 最后尝试查找第一个{到最后一个}之间的内容
                    first_brace = result_text.find('{')
                    last_brace = result_text.rfind('}')
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        result = json.loads(result_text[first_brace:last_brace+1])
                    else:
                        raise ValueError(f"无法解析JSON: {result_text[:200]}")

        except Exception as e:
            # 降级处理
            result = {
                "parsed_memory_type": "wonderful_moment",
                "parsed_title": "温暖的记忆",
                "parsed_content": raw_text[:100] if len(raw_text) > 100 else raw_text,
                "generated_item_name": f"{pet.get('name', 'ta')}的纪念",
                "generated_item_type": "heart",
                "ai_response": "汪~ 主人，记得呢",
                "relationship_materials": {"fixed_actions": [], "owner_phrases": [], "habits": []},
                "inferred_traits": [],
                "provenance": "user_reported"
            }

        # 保存口述记录
        cursor.execute("""
            INSERT INTO narration_records (pet_id, raw_text, parsed_memory_type, parsed_title, parsed_content,
                generated_item_name, generated_item_type, ai_response, is_processed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (pet_id, raw_text, result.get("parsed_memory_type"), result.get("parsed_title"),
              result.get("parsed_content"), result.get("generated_item_name"),
              result.get("generated_item_type"), result.get("ai_response")))
        narration_id = cursor.lastrowid

        # 存储关系素材
        rel_materials = result.get("relationship_materials", {})
        fixed_actions = rel_materials.get("fixed_actions", []) or []
        owner_phrases = rel_materials.get("owner_phrases", []) or []
        habits = rel_materials.get("habits", []) or []

        for action in fixed_actions:
            cursor.execute("""
                INSERT INTO relationship_materials (pet_id, material_type, content, source_narration_id, provenance, confidence)
                VALUES (?, 'fixed_action', ?, ?, 'user_reported', 1.0)
            """, (pet_id, action, narration_id))

        for phrase in owner_phrases:
            cursor.execute("""
                INSERT INTO relationship_materials (pet_id, material_type, content, source_narration_id, provenance, confidence)
                VALUES (?, 'owner_phrase', ?, ?, 'user_reported', 1.0)
            """, (pet_id, phrase, narration_id))

        for habit in habits:
            cursor.execute("""
                INSERT INTO relationship_materials (pet_id, material_type, content, source_narration_id, provenance, confidence)
                VALUES (?, 'habit', ?, ?, 'user_reported', 1.0)
            """, (pet_id, habit, narration_id))

        # 存储推断的性格特征
        inferred = result.get("inferred_traits", []) or []
        for trait in inferred:
            cursor.execute("""
                INSERT INTO inferred_traits (pet_id, trait, trait_category, source_memory_id, confidence)
                VALUES (?, ?, 'personality', ?, 0.7)
            """, (pet_id, trait, narration_id))

        cursor.execute("SELECT * FROM narration_records WHERE id = ?", (narration_id,))
        return dict_from_row(cursor.fetchone())

@router.get("/pets/{pet_id}/narrations", response_model=List[NarrationRecordResponse], tags=["Narration"])
def list_narrations(pet_id: int):
    """获取口述历史"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM narration_records WHERE pet_id = ? ORDER BY created_at DESC", (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.post("/pets/{pet_id}/narrations/auto-grow", tags=["Narration"])
def auto_grow_from_narration(pet_id: int, narration_text: str = Query(..., description="自然口述内容")):
    """
    自动生长：用户口述 → 自动创建记忆 → 自动生成物品 → 返回完整结果
    这是"让世界继续生长"的核心API
    """
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())
        if not pet:
            raise HTTPException(status_code=404, detail="Pet not found")

        # 解析口述
        try:
            from dotenv import load_dotenv
            load_dotenv(override=True)

            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "Qwen/Qwen3.6-27B"),
                        "messages": [{
                            "role": "user",
                            "content": f"""分析用户关于宠物"{pet.get('name', 'ta')}"的描述，提取信息并生成记忆和物品。

用户描述：{narration_text}

请以JSON格式返回：
{{
    "parsed_memory_type": "first_sight/funny_eating/departure_reaction/protection/protected_by_owner/wonderful_moment",
    "parsed_title": "5字以内的标题",
    "parsed_content": "完整描述（20字以上）",
    "generated_item_name": "生成的物品名称",
    "generated_item_type": "toy/food/photo/medal/heart/star/default",
    "ai_response": "AI的温柔回应（20字以内）",
    "relationship_materials": {{
        "fixed_actions": ["具体的行为链描述，如'等主人放包脱鞋后才慢吞吞过来'，最多2个"],
        "owner_phrases": ["主人经常说的固定用语，如'想我就直说嘛'，最多2个"],
        "habits": ["习惯性行为，如'一听到钥匙声就冲过来'，最多2个"]
    }},
    "inferred_traits": ["从行为推断的性格，如'嘴硬'/'贪吃'/'胆小'，最多2个"],
    "provenance": "user_reported"
}}

只返回JSON。"""
                        }],
                        "temperature": 0.3
                    }
                )
                response.raise_for_status()
                result = response.json()
                result_text = result["choices"][0]["message"]["content"]

            import json
            import re
            # 尝试直接解析，如果失败则尝试提取JSON块
            try:
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # 尝试提取JSON块（处理LLM返回的可能包含markdown代码块的情况）
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 最后尝试查找第一个{到最后一个}之间的内容
                    first_brace = result_text.find('{')
                    last_brace = result_text.rfind('}')
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        result = json.loads(result_text[first_brace:last_brace+1])
                    else:
                        raise ValueError(f"无法解析JSON: {result_text[:200]}")

        except Exception as e:
            result = {
                "parsed_memory_type": "wonderful_moment",
                "parsed_title": "温暖的记忆",
                "parsed_content": narration_text[:100] if len(narration_text) > 100 else narration_text,
                "generated_item_name": f"{pet.get('name', 'ta')}的纪念",
                "generated_item_type": "heart",
                "ai_response": "汪~ 主人，记得呢",
                "relationship_materials": {"fixed_actions": [], "owner_phrases": [], "habits": []},
                "inferred_traits": [],
                "provenance": "user_reported"
            }

        # 1. 创建记忆
        cursor.execute("""
            INSERT INTO memories (pet_id, memory_type, title, content, provenance, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (pet_id, result.get("parsed_memory_type"), result.get("parsed_title"),
              result.get("parsed_content"), result.get("provenance", "user_reported"), 1.0))
        memory_id = cursor.lastrowid
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        memory = dict_from_row(cursor.fetchone())

        # 2. 创建虚拟物品
        cursor.execute("""
            INSERT INTO virtual_home_items (pet_id, item_type, item_name, description, memory_id, growth_level)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (pet_id, result.get("generated_item_type"), result.get("generated_item_name"),
              f"来自记忆：{result.get('parsed_title')}", memory_id))
        item_id = cursor.lastrowid
        cursor.execute("SELECT * FROM virtual_home_items WHERE id = ?", (item_id,))
        item = dict_from_row(cursor.fetchone())

        # 3. 先保存口述记录，获取ID后再存储关系素材
        cursor.execute("""
            INSERT INTO narration_records (pet_id, raw_text, parsed_memory_type, parsed_title, parsed_content,
                generated_item_name, generated_item_type, ai_response, is_processed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (pet_id, narration_text, result.get("parsed_memory_type"), result.get("parsed_title"),
              result.get("parsed_content"), result.get("generated_item_name"),
              result.get("generated_item_type"), result.get("ai_response")))
        narration_record_id = cursor.lastrowid

        # 4. 存储关系素材
        rel_materials = result.get("relationship_materials", {})
        fixed_actions = rel_materials.get("fixed_actions", []) or []
        owner_phrases = rel_materials.get("owner_phrases", []) or []
        habits = rel_materials.get("habits", []) or []

        for action in fixed_actions:
            cursor.execute("""
                INSERT INTO relationship_materials (pet_id, material_type, content, source_narration_id, provenance, confidence)
                VALUES (?, 'fixed_action', ?, ?, 'user_reported', 1.0)
            """, (pet_id, action, narration_record_id))

        for phrase in owner_phrases:
            cursor.execute("""
                INSERT INTO relationship_materials (pet_id, material_type, content, source_narration_id, provenance, confidence)
                VALUES (?, 'owner_phrase', ?, ?, 'user_reported', 1.0)
            """, (pet_id, phrase, narration_record_id))

        for habit in habits:
            cursor.execute("""
                INSERT INTO relationship_materials (pet_id, material_type, content, source_narration_id, provenance, confidence)
                VALUES (?, 'habit', ?, ?, 'user_reported', 1.0)
            """, (pet_id, habit, narration_record_id))

        # 5. 存储推断的性格特征
        inferred = result.get("inferred_traits", []) or []
        for trait in inferred:
            cursor.execute("""
                INSERT INTO inferred_traits (pet_id, trait, trait_category, source_memory_id, confidence)
                VALUES (?, ?, 'personality', ?, 0.7)
            """, (pet_id, trait, memory_id))

        return {
            "ai_response": result.get("ai_response"),
            "created_memory": memory,
            "created_item": item,
            "growth_level": 1,
            "message": f"世界又生长了一点 ✨"
        }

# ============ Relationship Materials Endpoints ============

@router.get("/pets/{pet_id}/relationship-materials", response_model=List[RelationshipMaterialResponse], tags=["Relationship"])
def get_relationship_materials(pet_id: int, material_type: Optional[str] = None):
    """获取宠物的关系素材"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        if material_type:
            cursor.execute("""
                SELECT * FROM relationship_materials
                WHERE pet_id = ? AND material_type = ? AND is_active = 1
                ORDER BY confidence DESC, created_at DESC
            """, (pet_id, material_type))
        else:
            cursor.execute("""
                SELECT * FROM relationship_materials
                WHERE pet_id = ? AND is_active = 1
                ORDER BY confidence DESC, created_at DESC
            """, (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.get("/pets/{pet_id}/inferred-traits", response_model=List[InferredTraitResponse], tags=["Relationship"])
def get_inferred_traits(pet_id: int):
    """获取宠物的推断性格特征"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            SELECT * FROM inferred_traits
            WHERE pet_id = ? ORDER BY confidence DESC, created_at DESC
        """, (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

@router.get("/pets/{pet_id}/puppyland-shared", response_model=List[PuppylandSharedResponse], tags=["Relationship"])
def get_puppyland_shared(pet_id: int, shared_type: Optional[str] = None):
    """获取在Puppyland中共同创造的内容"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        if shared_type:
            cursor.execute("""
                SELECT * FROM puppyland_shared
                WHERE pet_id = ? AND shared_type = ?
                ORDER BY usage_count DESC, created_at DESC
            """, (pet_id, shared_type))
        else:
            cursor.execute("""
                SELECT * FROM puppyland_shared
                WHERE pet_id = ? ORDER BY usage_count DESC, created_at DESC
            """, (pet_id,))
        return [dict_from_row(row) for row in cursor.fetchall()]

# ============ ASR (语音识别) ============

@router.get("/asr", tags=["ASR"])
def get_asr_url(voice_id: str = Query(default="", description="语音ID")):
    """签出腾讯云实时语音识别的 WebSocket 连接串，供前端直接连。

    前端拿 url 建 WebSocket，逐片推 PCM 音频，收 JSON 转写结果。
    SecretKey 不下发浏览器，由后端签名。
    """
    from backend_app.realtime_asr import build_asr_connect_url
    try:
        out = build_asr_connect_url(voice_id or None)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return out


@router.get("/extract-pet-info", tags=["ASR"])
def extract_pet_info(text: str = Query(..., description="用户口述的原始文本")):
    """
    从用户口述文本中提取宠物信息（名字、品种、性格等）。
    优先使用 LLM 提取名字及其他信息；LLM 未返回有效名字时，再回退到规则提取。

    设计：支持增量更新——如果 pet_name 已存在，只在未提取到时才覆盖。
    """
    import re, os
    from dotenv import load_dotenv
    load_dotenv(override=True)

    # ── Step 1: 正则提取名字 ───────────────────────────────────────
    # 常见模式：我家叫 X / X 是一只 / 它叫 X / 名字是 X / 叫 X（狗名/小名）
    NAME_PATTERNS = [
        r'它叫([A-Za-z一-鿿]{1,8})',
        r'她叫([A-Za-z一-鿿]{1,8})',
        r'他叫([A-Za-z一-鿿]{1,8})',
        r'名字[是为是] ?([A-Za-z一-鿿]{1,8})',
        r'叫([A-Za-z一-鿿]{1,8})(?:这只|这只狗|的小狗|是一只|它)?',
        r'我家(?:小狗|狗|TA|它)叫([A-Za-z一-鿿]{1,8})',
        r'^([A-Za-z一-鿿]{1,8})(?:是|这只|的小狗)',
        r'(?:小狗|狗|TA|它)(?:叫|名字是) ?([A-Za-z一-鿿]{1,8})',
    ]

    fallback_name = None
    for pat in NAME_PATTERNS:
        m = re.search(pat, text)
        if m:
            candidate = m.group(1).strip()
            # 过滤掉明显不是名字的词
            if candidate and len(candidate) >= 2 and candidate not in ('一只', '这只', '的小狗', '一只狗', '什么', '名字'):
                fallback_name = candidate
                break

    # ── Step 2: LLM 优先提取名字及其他信息 ─────────────────────────
    extracted_name = None
    breed = None
    color = None
    personality_traits = []
    key_objects = []
    habits = []

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                os.getenv("base_url") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('api_key')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.getenv("model", "Qwen/Qwen3.6-27B"),
                    "messages": [{
                        "role": "user",
                        "content": f"""分析以下关于宠物（很可能是狗狗）的描述文本，提取信息。

描述：{text}

请以JSON格式返回：
{{
    "name": "宠物名字；只有文本明确提到名字时填写，否则为 null",
    "breed": "狗的品种，如柯基/金毛/泰迪/中华田园犬/拉布拉多/哈士奇/柴犬/法斗/吉娃娃/马尔济斯/边牧，或 null（未提及）",
    "color": "主要毛色，如白色/黄色/黑色/棕色/灰色/奶油色/花色，或 null",
    "personality_traits": ["性格关键词列表，如胆小/黏人/贪吃/活泼/安静/爱叫/聪明/调皮/忠诚/倔强，最多3个"],
    "key_objects": ["描述中提到的宠物用品/玩具，如球/骨头/玩具/毯子/窝，最多2个"],
    "habits": ["描述中提到的宠物习惯，如转圈/扑人/等门/晒太阳/护食，最多2个"],
    "fixed_actions": ["具体的行为链描述，如'等主人放包脱鞋后才慢吞吞过来'/'一听到钥匙声就冲过来'，最多2个"],
    "owner_phrases": ["主人经常对宠物说的固定用语，如'想我就直说嘛'/'肉肉好了'，最多2个"]
}}

只返回JSON。"""
                    }],
                    "temperature": 0.2
                }
            )
            response.raise_for_status()
            result = response.json()
            result_text = result["choices"][0]["message"]["content"]

        result = parse_llm_json_response(result_text)
        candidate_name = result.get("name") or result.get("pet_name") or result.get("extracted_name")
        if isinstance(candidate_name, str):
            candidate_name = candidate_name.strip()
            if candidate_name and len(candidate_name) <= 20 and candidate_name not in ('一只', '这只', '的小狗', '一只狗', '什么', '名字', 'null'):
                extracted_name = candidate_name
        breed = result.get("breed")
        color = result.get("color")
        personality_traits = result.get("personality_traits") or []
        key_objects = result.get("key_objects") or []
        habits = result.get("habits") or []
        fixed_actions = result.get("fixed_actions") or []
        owner_phrases = result.get("owner_phrases") or []

    except Exception as e:
        pass  # 网络错误时降级到规则提取名字

    # 仅当 LLM 没有给出有效名字时使用规则结果。
    if not extracted_name:
        extracted_name = fallback_name

    return {
        "extracted_name": extracted_name,
        "breed": breed,
        "color": color,
        "personality_traits": personality_traits,
        "key_objects": key_objects,
        "habits": habits,
        "fixed_actions": fixed_actions if 'fixed_actions' in dir() else [],
        "owner_phrases": owner_phrases if 'owner_phrases' in dir() else [],
        "raw_text": text
    }

# ============ Daily Letter Endpoints (每日信件) ============

@router.get("/pets/{pet_id}/daily-letter", response_model=DailyLetterResponse, tags=["DailyLetter"])
def get_daily_letter(pet_id: int, letter_date: Optional[str] = Query(None, description="信件日期，格式YYYY-MM-DD，不传则默认今天")):
    """
    获取指定日期的每日信件
    - 如果日期不存在，生成默认信件
    - 如果有新的聊天记录（比生成时多3条以上），自动重新生成个性化信件
    """
    from datetime import datetime
    from backend_app.database import get_db_connection

    if not letter_date:
        letter_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            SELECT * FROM daily_letters WHERE pet_id = ? AND letter_date = ?
        """, (pet_id, letter_date))
        row = cursor.fetchone()

        if row:
            # 检查是否需要基于新聊天重新生成
            cursor.execute("""
                SELECT COUNT(*) FROM chat_messages
                WHERE pet_id = ? AND date(created_at) = ?
            """, (pet_id, letter_date))
            current_chat_count = cursor.fetchone()[0]
            letter_chat_count = row['based_on_chat_count'] or 0

            # 如果当前聊天数比生成时多了8条以上，重新生成（无论是否已有个性化信件）
            chat_growth = current_chat_count - letter_chat_count
            should_regenerate = (chat_growth >= 8)

            if should_regenerate:
                # 收集所有需要的数据
                cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
                pet = dict_from_row(cursor.fetchone())

                cursor.execute("""
                    SELECT material_type, content FROM relationship_materials
                    WHERE pet_id = ? AND is_active = 1 ORDER BY confidence DESC
                """, (pet_id,))
                materials = cursor.fetchall()
                fixed_actions = [m[1] for m in materials if m[0] == 'fixed_action']
                owner_phrases = [m[1] for m in materials if m[0] == 'owner_phrase']
                habits = [m[1] for m in materials if m[0] == 'habit']

                cursor.execute("""
                    SELECT trait FROM inferred_traits WHERE pet_id = ? ORDER BY confidence DESC LIMIT 5
                """, (pet_id,))
                traits = [r[0] for r in cursor.fetchall()]

                cursor.execute("""
                    SELECT content FROM chat_messages
                    WHERE pet_id = ? AND date(created_at) = ?
                    ORDER BY created_at DESC LIMIT 5
                """, (pet_id, letter_date))
                recent_chats = [r[0] for r in cursor.fetchall()]

                old_letter_id = row['id']
                pet_name = pet.get('name', 'TA') if pet else 'TA'

                # 关闭连接后再调用LLM
                conn.commit()
                conn.close()

                # 生成新内容
                content = _generate_letter_content(
                    pet_name, traits, fixed_actions, owner_phrases, habits, recent_chats,
                    is_personalized=True
                )

                # 重新连接并保存
                conn2 = get_db_connection()
                try:
                    cursor2 = conn2.cursor()
                    cursor2.execute("DELETE FROM daily_letters WHERE id = ?", (old_letter_id,))
                    cursor2.execute("""
                        INSERT INTO daily_letters (pet_id, letter_date, content, is_generated, based_on_chat_count)
                        VALUES (?, ?, ?, 1, ?)
                    """, (pet_id, letter_date, content, current_chat_count))
                    letter_id = cursor2.lastrowid
                    cursor2.execute("SELECT * FROM daily_letters WHERE id = ?", (letter_id,))
                    result = dict_from_row(cursor2.fetchone())
                finally:
                    conn2.close()
                return result

            cursor.execute("SELECT * FROM daily_letters WHERE id = ?", (row['id'],))
            result = dict_from_row(cursor.fetchone())
            conn.commit()
            conn.close()
            return result

        conn.commit()
        conn.close()
        # 如果没有当天的信件，生成默认信件
        return _generate_default_letter(pet_id, letter_date)
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        raise

        # 如果没有当天的信件，生成默认信件
        return _generate_default_letter(pet_id, letter_date)


def _generate_default_letter(pet_id: int, letter_date: str) -> dict:
    """生成默认信件内容"""
    import os
    from datetime import datetime
    from dotenv import load_dotenv
    load_dotenv(override=True)

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())

        # 获取关系素材
        cursor.execute("""
            SELECT material_type, content FROM relationship_materials
            WHERE pet_id = ? AND is_active = 1 ORDER BY confidence DESC LIMIT 5
        """, (pet_id,))
        materials = cursor.fetchall()

        # 获取性格特征
        cursor.execute("""
            SELECT trait FROM inferred_traits WHERE pet_id = ? ORDER BY confidence DESC LIMIT 3
        """, (pet_id,))
        traits = [row[0] for row in cursor.fetchall()]

        pet_name = pet.get('name', 'TA') if pet else 'TA'

        # 生成默认信件prompt
        prompt = f"""你是{pet_name}，一只已经离开的小狗。请以小狗的口吻，写一封给主人的每日信件。

要求：
1. 温暖、治愈的风格
2. 30-50字左右
3. 以"我最爱的主人："开头
4. 不要提及具体日期或时间
5. 表达对主人的思念和陪伴

请直接返回信件内容，不要加引号或任何格式。"""

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "deepseek-v4-pro"),
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.8,
                        "max_tokens": 200
                    }
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            content = f"我最爱的主人：今天也很好。记得我一直在。{pet_name}"

        # 保存到数据库
        cursor.execute("""
            INSERT INTO daily_letters (pet_id, letter_date, content, is_generated, based_on_chat_count)
            VALUES (?, ?, ?, 0, 0)
        """, (pet_id, letter_date, content))
        letter_id = cursor.lastrowid

        cursor.execute("SELECT * FROM daily_letters WHERE id = ?", (letter_id,))
        return dict_from_row(cursor.fetchone())


def _generate_letter_content(pet_name: str, traits: list, fixed_actions: list,
                              owner_phrases: list, habits: list, recent_chats: list,
                              is_personalized: bool = False) -> str:
    """生成信件内容的辅助函数（不涉及数据库操作）"""
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)

    if is_personalized and recent_chats:
        prompt = f"""你是{pet_name}，一只已经离开的小狗。请以小狗的口吻，写一封给主人的每日信件。

宠物的名字：{pet_name}
性格特征：{', '.join(traits) if traits else '可爱'}

关系素材（这些是你们之间真实发生过的事）：
{chr(10).join([f"- {a}" for a in fixed_actions[:3]]) if fixed_actions else "- 陪伴主人"}
主人常说的话：{', '.join([f'"{p}"' for p in owner_phrases[:2]]) if owner_phrases else '无'}
习惯：{', '.join([f"{h}" for h in habits[:2]]) if habits else '无'}

今天的聊天内容：
{chr(10).join([f"- {c}" for c in recent_chats]) if recent_chats else '无'}

要求：
1. 温暖、治愈的风格，30-80字左右
2. 以"我最爱的主人："开头
3. 贴合上述关系素材和聊天内容，不要复述，要自然承接
4. 不要提及具体日期
5. 信件风格参考：提到某些具体的习惯或动作，表达思念和陪伴

请直接返回信件内容，不要加引号或任何格式。"""
    else:
        prompt = f"""你是{pet_name}，一只已经离开的小狗。请以小狗的口吻，写一封给主人的每日信件。

要求：
1. 温暖、治愈的风格
2. 30-50字左右
3. 以"我最爱的主人："开头
4. 不要提及具体日期或时间
5. 表达对主人的思念和陪伴

请直接返回信件内容，不要加引号或任何格式。"""

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                os.getenv("base_url") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('api_key')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.getenv("model", "deepseek-v4-pro"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.8,
                    "max_tokens": 300
                }
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"我最爱的主人：今天也很好。记得我一直在。{pet_name}"


def _generate_personalized_letter(pet_id: int, letter_date: str, current_chat_count: int) -> dict:
    """基于聊天增量重新生成个性化信件"""
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())

        # 获取关系素材
        cursor.execute("""
            SELECT material_type, content FROM relationship_materials
            WHERE pet_id = ? AND is_active = 1 ORDER BY confidence DESC
        """, (pet_id,))
        materials = cursor.fetchall()
        fixed_actions = [row[1] for row in materials if row[0] == 'fixed_action']
        owner_phrases = [row[1] for row in materials if row[0] == 'owner_phrase']
        habits = [row[1] for row in materials if row[0] == 'habit']

        # 获取性格特征
        cursor.execute("""
            SELECT trait FROM inferred_traits WHERE pet_id = ? ORDER BY confidence DESC LIMIT 5
        """, (pet_id,))
        traits = [row[0] for row in cursor.fetchall()]

        # 获取当天的聊天记录
        cursor.execute("""
            SELECT content FROM chat_messages
            WHERE pet_id = ? AND date(created_at) = ?
            ORDER BY created_at DESC LIMIT 5
        """, (pet_id, letter_date))
        recent_chats = [row[0] for row in cursor.fetchall()]

        pet_name = pet.get('name', 'TA') if pet else 'TA'

        letters_prompt = f"""你是{pet_name}，一只已经离开的小狗。请以小狗的口吻，写一封给主人的每日信件。

宠物的名字：{pet_name}
性格特征：{', '.join(traits) if traits else '可爱'}

关系素材（这些是你们之间真实发生过的事）：
{chr(10).join([f"- {a}" for a in fixed_actions[:3]]) if fixed_actions else "- 陪伴主人"}
主人常说的话：{', '.join([f'"{p}"' for p in owner_phrases[:2]]) if owner_phrases else '无'}
习惯：{', '.join([f"{h}" for h in habits[:2]]) if habits else '无'}

今天的聊天内容：
{chr(10).join([f"- {c}" for c in recent_chats]) if recent_chats else '无'}

要求：
1. 温暖、治愈的风格，30-80字左右
2. 以"我最爱的主人："开头
3. 贴合上述关系素材和聊天内容，不要复述，要自然承接
4. 不要提及具体日期
5. 信件风格参考：提到某些具体的习惯或动作，表达思念和陪伴

请直接返回信件内容，不要加引号或任何格式。"""

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "deepseek-v4-pro"),
                        "messages": [{"role": "user", "content": letters_prompt}],
                        "temperature": 0.8,
                        "max_tokens": 300
                    }
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            content = f"我最爱的主人：今天也很好。记得我一直在。{pet_name}"

        # 保存到数据库
        cursor.execute("""
            INSERT INTO daily_letters (pet_id, letter_date, content, is_generated, based_on_chat_count)
            VALUES (?, ?, ?, 1, ?)
        """, (pet_id, letter_date, content, current_chat_count))
        letter_id = cursor.lastrowid

        cursor.execute("SELECT * FROM daily_letters WHERE id = ?", (letter_id,))
        return dict_from_row(cursor.fetchone())


@router.post("/pets/{pet_id}/daily-letter/generate", response_model=DailyLetterResponse, tags=["DailyLetter"])
def generate_daily_letter(pet_id: int, request: GenerateLetterRequest = None):
    """
    手动触发生成当日的每日信件
    根据当天聊天记录数量决定生成个性化信件还是默认信件
    聊天记录>=3条时生成个性化信件
    """
    import os
    from datetime import datetime
    from dotenv import load_dotenv
    load_dotenv(override=True)

    letter_date = request.letter_date if request and request.letter_date else datetime.now().strftime("%Y-%m-%d")

    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        # 获取当天的聊天记录数量
        cursor.execute("""
            SELECT COUNT(*) FROM chat_messages
            WHERE pet_id = ? AND date(created_at) = ?
        """, (pet_id, letter_date))
        chat_count = cursor.fetchone()[0]

        # 获取宠物信息
        cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
        pet = dict_from_row(cursor.fetchone())

        # 获取关系素材
        cursor.execute("""
            SELECT material_type, content FROM relationship_materials
            WHERE pet_id = ? AND is_active = 1 ORDER BY confidence DESC
        """, (pet_id,))
        materials = cursor.fetchall()
        fixed_actions = [row[1] for row in materials if row[0] == 'fixed_action']
        owner_phrases = [row[1] for row in materials if row[0] == 'owner_phrase']
        habits = [row[1] for row in materials if row[0] == 'habit']

        # 获取性格特征
        cursor.execute("""
            SELECT trait FROM inferred_traits WHERE pet_id = ? ORDER BY confidence DESC LIMIT 5
        """, (pet_id,))
        traits = [row[0] for row in cursor.fetchall()]

        # 获取最近的聊天记录（用于生成个性化内容）
        cursor.execute("""
            SELECT content FROM chat_messages
            WHERE pet_id = ? AND date(created_at) = ?
            ORDER BY created_at DESC LIMIT 5
        """, (pet_id, letter_date))
        recent_chats = [row[0] for row in cursor.fetchall()]

        pet_name = pet.get('name', 'TA') if pet else 'TA'

        # 根据聊天记录数量决定生成内容
        if chat_count >= 3:
            # 生成个性化信件
            letters_prompt = f"""你是{pet_name}，一只已经离开的小狗。请以小狗的口吻，写一封给主人的每日信件。

宠物的名字：{pet_name}
性格特征：{', '.join(traits) if traits else '可爱'}

关系素材（这些是你们之间真实发生过的事）：
{chr(10).join([f"- {a}" for a in fixed_actions[:3]]) if fixed_actions else "- 陪伴主人"}
主人常说的话：{', '.join([f'"{p}"' for p in owner_phrases[:2]]) if owner_phrases else '无'}
习惯：{', '.join([f"{h}" for h in habits[:2]]) if habits else '无'}

今天的聊天内容：
{chr(10).join([f"- {c}" for c in recent_chats]) if recent_chats else '无'}

要求：
1. 温暖、治愈的风格，30-80字左右
2. 以"我最爱的主人："开头
3. 贴合上述关系素材和聊天内容，不要复述，要自然承接
4. 不要提及具体日期
5. 信件风格参考：提到某些具体的习惯或动作，表达思念和陪伴

请直接返回信件内容，不要加引号或任何格式。"""
        else:
            # 生成默认信件
            letters_prompt = f"""你是{pet_name}，一只已经离开的小狗。请以小狗的口吻，写一封给主人的每日信件。

要求：
1. 温暖、治愈的风格，30-50字左右
2. 以"我最爱的主人："开头
3. 不要提及具体日期
4. 表达对主人的思念和陪伴

请直接返回信件内容，不要加引号或任何格式。"""

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    os.getenv("base_url") + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": os.getenv("model", "deepseek-v4-pro"),
                        "messages": [{"role": "user", "content": letters_prompt}],
                        "temperature": 0.8,
                        "max_tokens": 300
                    }
                )
                response.raise_for_status()
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            content = f"我最爱的主人：今天也很好。记得我一直在。{pet_name}"

        # 删除旧信件（如果存在）
        cursor.execute("""
            DELETE FROM daily_letters WHERE pet_id = ? AND letter_date = ?
        """, (pet_id, letter_date))

        # 保存新信件
        cursor.execute("""
            INSERT INTO daily_letters (pet_id, letter_date, content, is_generated, based_on_chat_count)
            VALUES (?, ?, ?, ?, ?)
        """, (pet_id, letter_date, content, 1 if chat_count >= 3 else 0, chat_count))
        letter_id = cursor.lastrowid

        cursor.execute("SELECT * FROM daily_letters WHERE id = ?", (letter_id,))
        return dict_from_row(cursor.fetchone())


@router.get("/pets/{pet_id}/daily-letter/history", response_model=List[DailyLetterResponse], tags=["DailyLetter"])
def get_letter_history(pet_id: int, limit: int = Query(7, ge=1, le=30)):
    """获取最近的信件历史"""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pets WHERE id = ?", (pet_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pet not found")

        cursor.execute("""
            SELECT * FROM daily_letters WHERE pet_id = ?
            ORDER BY letter_date DESC LIMIT ?
        """, (pet_id, limit))
        return [dict_from_row(row) for row in cursor.fetchall()]

# ============ Dog Image Generation ============

import os
import base64
import re
from PIL import Image
import io
from fastapi import UploadFile, File

BREEDS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prototype", "assets", "breeds")
THREEVIEWS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prototype", "assets", "threeviews")


def _extract_dominant_color(image_path: str) -> tuple:
    """提取图片的主导颜色 (R, G, B)"""
    try:
        img = Image.open(image_path).convert("RGB")
        img = img.resize((50, 50))
        pixels = list(img.getdata())
        # 简单的平均色
        r = int(sum(p[0] for p in pixels) / len(pixels))
        g = int(sum(p[1] for p in pixels) / len(pixels))
        b = int(sum(p[2] for p in pixels) / len(pixels))
        return (r, g, b)
    except Exception:
        return (128, 128, 128)


def _color_distance(c1: tuple, c2: tuple) -> float:
    """计算两个颜色的欧氏距离"""
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2) ** 0.5


def _text_similarity(name1: str, name2: str) -> float:
    """计算两个字符串的文字相似度（简单的字符级Jaccard）"""
    s1 = set(name1.lower())
    s2 = set(name2.lower())
    if not s1 or not s2:
        return 0.0
    intersection = len(s1 & s2)
    union = len(s1 | s2)
    return intersection / union if union > 0 else 0.0


def _find_closest_breeds_by_color(user_image_base64: str) -> list:
    """根据用户上传图片的颜色，找到breeds目录中最接近的2个品种"""
    try:
        # 解码用户图片
        img_data = base64.b64decode(user_image_base64)
        user_img = Image.open(io.BytesIO(img_data)).convert("RGB").resize((50, 50))
        user_pixels = list(user_img.getdata())
        user_r = int(sum(p[0] for p in user_pixels) / len(user_pixels))
        user_g = int(sum(p[1] for p in user_pixels) / len(user_pixels))
        user_b = int(sum(p[2] for p in user_pixels) / len(user_pixels))
        user_color = (user_r, user_g, user_b)
    except Exception:
        return []

    # 获取所有breed图片的颜色
    breeds_colors = []
    for fname in os.listdir(BREEDS_DIR):
        if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        fpath = os.path.join(BREEDS_DIR, fname)
        color = _extract_dominant_color(fpath)
        breeds_colors.append((fname, color))

    # 按颜色距离排序，取最近的2个
    breeds_colors.sort(key=lambda x: _color_distance(x[1], user_color))
    return [os.path.splitext(item[0])[0] for item in breeds_colors[:2]]


def _find_closest_breeds_by_text(voice_description: str) -> list:
    """根据文字相似度，从voice_description中找品种名，然后匹配breeds目录"""
    # 提取描述中的品种关键词
    breed_keywords = [
        "拉布拉多", " Labrador", "labrador",
        "金毛", "金毛猎犬", "Golden Retriever", "golden retriever",
        "柯基", "威尔士柯基", "corgi", "Corgi",
        "柴犬", "shiba", "Shiba",
        "哈士奇", "husky", "Husky",
        "边牧", "边境牧羊犬", "Border Collie", "border collie",
        "法斗", "法国斗牛犬", "French Bulldog", "french bulldog",
        "吉娃娃", "Chihuahua", "chihuahua",
        "泰迪", "贵宾犬", "Poodle", "poodle",
        "比格犬", "米格鲁", "Beagle", "beagle",
        "萨摩耶", "Samoyed", "samoyed",
        "斑点狗", "大麦町", "Dalmatian", "dalmatian",
        "中华田园犬", "土狗", "田园犬",
        "雪纳瑞", "Schnauzer", "schnauzer",
        "约克夏", "Yorkie", "yorkie",
        "腊肠", "Dachshund", "dachshund",
        "西施犬", "西施", "Shih Tzu", "shih tzu",
        "德牧", "德国牧羊犬", "German Shepherd", "german shepherd",
        "杰克罗素梗", "Jack Russell", "jack russell", "罗素梗",
    ]

    voice_lower = voice_description.lower()
    best_match = None
    best_score = 0.0

    for kw in breed_keywords:
        score = _text_similarity(voice_lower, kw.lower())
        if score > best_score:
            best_score = score
            best_match = kw

    # 标准化品种名到breeds文件名
    breed_name_map = {
        "拉布拉多": "拉布拉多", "labrador": "拉布拉多", "labrador": "拉布拉多",
        "金毛": "金毛", "golden retriever": "金毛",
        "柯基": "柯基", "corgi": "柯基",
        "柴犬": "柴犬", "shiba": "柴犬",
        "哈士奇": "哈士奇", "husky": "哈士奇",
        "边牧": "边牧", "border collie": "边牧",
        "法斗": "法斗", "french bulldog": "法斗",
        "吉娃娃": "吉娃娃", "chihuahua": "吉娃娃",
        "泰迪": "泰迪", "poodle": "泰迪",
        "比格犬": "比格犬", "beagle": "比格犬",
        "萨摩耶": "萨摩耶", "samoyed": "萨摩耶",
        "斑点狗": "斑点狗", "dalmatian": "斑点狗",
        "中华田园犬": "中华田园犬", "土狗": "中华田园犬",
        "雪纳瑞": "雪纳瑞", "schnauzer": "雪纳瑞",
        "约克夏": "约克夏", "yorkie": "约克夏",
        "腊肠": "腊肠", "dachshund": "腊肠",
        "西施犬": "西施犬", "shih tzu": "西施犬",
        "德牧": "德牧", "german shepherd": "德牧",
        "杰克罗素梗": "比格犬", "jack russell": "比格犬", "罗素梗": "比格犬",
    }

    # 从描述中提取品种名
    found_breeds = []
    desc_lower = voice_description.lower()

    # 精确匹配品种名（中文）
    for fname in os.listdir(BREEDS_DIR):
        breed_name = os.path.splitext(fname)[0]
        if breed_name in voice_description:
            if breed_name not in found_breeds:
                found_breeds.append(breed_name)

    # 如果没有精确匹配，用关键词匹配
    if not found_breeds:
        for kw, mapped in breed_name_map.items():
            if kw.lower() in desc_lower:
                if mapped not in found_breeds:
                    found_breeds.append(mapped)

    # 如果找到1个，再用文字相似度找第2个
    if found_breeds:
        target_name = found_breeds[0]
        # 找与目标相似度最高的另一个
        best_second = None
        best_second_score = 0.0
        for fname in os.listdir(BREEDS_DIR):
            breed_name = os.path.splitext(fname)[0]
            if breed_name == target_name or breed_name in found_breeds:
                continue
            score = _text_similarity(target_name, breed_name)
            if score > best_second_score:
                best_second_score = score
                best_second = breed_name
        if best_second:
            found_breeds.append(best_second)

    # 如果仍然不足2个，用文字相似度从描述中找
    if len(found_breeds) < 2:
        all_breeds = [os.path.splitext(f)[0] for f in os.listdir(BREEDS_DIR)
                      if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        desc_for_sim = voice_description
        scored = [(b, _text_similarity(desc_for_sim, b)) for b in all_breeds]
        scored.sort(key=lambda x: x[1], reverse=True)
        for b, s in scored:
            if b not in found_breeds:
                found_breeds.append(b)
            if len(found_breeds) >= 2:
                break

    return found_breeds[:2]


def _remove_green_background(img_bytes: bytes) -> bytes:
    """抠掉绿色背景，使用HSV颜色空间 chroma key"""
    try:
        import numpy as np
        from PIL import Image
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(img, dtype=np.float32) / 255.0
        r_g = arr[:, :, 0]
        g_g = arr[:, :, 1]
        b_g = arr[:, :, 2]
        max_c = np.maximum(np.maximum(r_g, g_g), b_g)
        min_c = np.minimum(np.minimum(r_g, g_g), b_g)
        delta = max_c - min_c
        h = np.zeros_like(max_c)
        mask_delta = delta > 1e-8
        idx_r = mask_delta & (max_c == r_g)
        idx_g = mask_delta & (max_c == g_g)
        idx_b = mask_delta & (max_c == b_g)
        h[idx_r] = 60.0 * (((g_g[idx_r] - b_g[idx_r]) / (delta[idx_r] + 1e-8)) % 6.0)
        h[idx_g] = 60.0 * ((b_g[idx_g] - r_g[idx_g]) / (delta[idx_g] + 1e-8) + 2.0)
        h[idx_b] = 60.0 * ((r_g[idx_b] - g_g[idx_b]) / (delta[idx_b] + 1e-8) + 4.0)
        h = h / 360.0
        s = np.where(max_c > 1e-8, delta / (max_c + 1e-8), 0.0)
        v = max_c
        green_mask = (h >= 0.18) & (h <= 0.48) & (s > 0.15) & (v > 0.15)
        light_green = (h >= 0.18) & (h <= 0.50) & (s > 0.05) & (v > 0.70)
        green_mask = green_mask | light_green
        rgba_arr = np.zeros((img.size[1], img.size[0], 4), dtype=np.uint8)
        rgba_arr[:, :, :3] = (arr * 255).astype(np.uint8)
        rgba_arr[:, :, 3] = 255
        rgba_arr[green_mask, 3] = 0
        result = Image.fromarray(rgba_arr, mode='RGBA')
        output = io.BytesIO()
        result.save(output, format="PNG")
        return output.getvalue()
    except Exception:
        return img_bytes


def _remove_beige_background(img_bytes: bytes) -> bytes:
    """抠掉米色背景 RGB(251,232,207)，使用 LAB 颜色空间 chroma key

    图片正中央 150x150 像素始终落在狗狗身体范围内（三视图构图居中生成），
    这一区域强制保留不透明，防止奶油色皮毛/高光等与背景色相近时被误判
    为背景而在狗狗身体内部抠出空洞。
    """
    try:
        import numpy as np
        from PIL import Image

        # 目标背景色
        TARGET_R, TARGET_G, TARGET_B = 251.0, 232.0, 207.0
        # 容差（AI生成的背景会有轻微偏差）
        TOLERANCE = 45.0
        # 中央保护区域边长（像素）：该范围始终在狗狗轮廓内，禁止被抠除
        PROTECT_SIZE = 150

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(img, dtype=np.float32)
        h, w = arr.shape[0], arr.shape[1]

        # 计算每个像素到目标背景色的欧氏距离
        dist = np.sqrt(
            (arr[:, :, 0] - TARGET_R) ** 2 +
            (arr[:, :, 1] - TARGET_G) ** 2 +
            (arr[:, :, 2] - TARGET_B) ** 2
        )

        # 掩码：距离小于容差
        mask = dist <= TOLERANCE

        # 边缘膨胀：扩大背景掩码，防止残留边缘
        # 对掩码进行简单膨胀（2次迭代）
        for _ in range(2):
            mask = mask | np.roll(mask, 1, axis=0) | np.roll(mask, -1, axis=0)
            mask = mask | np.roll(mask, 1, axis=1) | np.roll(mask, -1, axis=1)

        # 中央保护区域：图片正中 150x150 像素落在狗狗身体内，膨胀后
        # 再强制清除该区域的背景标记，确保不会被误抠透明
        half = PROTECT_SIZE // 2
        cy, cx = h // 2, w // 2
        y0, y1 = max(0, cy - half), min(h, cy + (PROTECT_SIZE - half))
        x0, x1 = max(0, cx - half), min(w, cx + (PROTECT_SIZE - half))
        mask[y0:y1, x0:x1] = False

        # 转 RGBA
        rgba_arr = np.zeros((img.size[1], img.size[0], 4), dtype=np.uint8)
        rgba_arr[:, :, :3] = arr.astype(np.uint8)
        rgba_arr[:, :, 3] = 255
        rgba_arr[mask, 3] = 0

        result = Image.fromarray(rgba_arr, mode='RGBA')
        output = io.BytesIO()
        result.save(output, format="PNG")
        return output.getvalue()
    except Exception:
        return img_bytes


def _get_threeview_path(breed_name: str) -> str:
    """获取品种对应的三视图文件路径"""
    possible_names = [breed_name, breed_name + "三视图"]
    for name in possible_names:
        fpath = os.path.join(THREEVIEWS_DIR, name + ".png")
        if os.path.exists(fpath):
            return fpath
    # 模糊匹配
    for fname in os.listdir(THREEVIEWS_DIR):
        if breed_name in fname or fname.replace("三视图", "") == breed_name:
            return os.path.join(THREEVIEWS_DIR, fname)
    return None


@router.post("/generate-dog-image", tags=["AI"])
async def generate_dog_image(request: GenerateDogImageRequest):
    """
    根据用户描述和可选图片，生成狗狗形象图片。
    流程：
    1. 若有上传图片 → 按颜色相似度匹配2个breed
    2. 若无上传图片 → 从描述中提取品种名，按文字相似度匹配2个breed
    3. 调用AI图生图（以2个breed的三视图为参考）
    4. 抠掉绿色背景，返回透明PNG
    """
    voice_description = request.voice_description
    has_photo = request.has_uploaded_photo
    uploaded_b64 = request.uploaded_photo_base64

    # Step 1 & 2: 找到最接近的2个品种
    if has_photo and uploaded_b64:
        breed_names = _find_closest_breeds_by_color(uploaded_b64)
    else:
        breed_names = _find_closest_breeds_by_text(voice_description)

    if len(breed_names) < 2:
        return {
            "success": False,
            "message": f"无法找到足够的匹配品种，找到: {breed_names}",
            "breed_names": breed_names,
            "image_base64": None
        }

    # Step 3: 获取三视图路径
    threeview_paths = []
    for bn in breed_names:
        path = _get_threeview_path(bn)
        if path:
            threeview_paths.append(path)

    if not threeview_paths:
        return {
            "success": False,
            "message": f"未找到品种对应的三视图: {breed_names}",
            "breed_names": breed_names,
            "image_base64": None
        }

    # 读取三视图base64
    threeview_b64s = []
    for p in threeview_paths:
        with open(p, "rb") as f:
            threeview_b64s.append(f"data:image/png;base64,{base64.b64encode(f.read()).decode()}")

    # Step 4: 构造提示词
    breed_display = "、".join(breed_names)
    if has_photo and uploaded_b64:
        prompt = (
            f"参考三视图是{breed_display}品种的示例图，风格为奶油肌理卡通画风，姿态固定。\n"
            f"生成一只{breed_display}品种狗的三视图主视图（正面视角），"
            f"以奶油肌理卡通画风呈现，色彩温暖柔和，笔触细腻带有轻微肌理感，造型可爱圆润。\n"
            f"这只狗的特征描述：{voice_description}。\n"
            f"用户上传的图片仅用于颜色和花纹的参考（颜色深浅、花纹分布），不得改变品种特征和整体造型。\n"
            f"动作姿态严格遵循参考三视图，不生成汉字，背景颜色改为RGB(251,232,207)"
        )
    else:
        prompt = (
            f"参考三视图是{breed_display}品种的示例图，风格为奶油肌理卡通画风，姿态固定。\n"
            f"生成一只{breed_display}品种狗的三视图主视图（正面视角），"
            f"以奶油肌理卡通画风呈现，色彩温暖柔和，笔触细腻带有轻微肌理感，造型可爱圆润。\n"
            f"这只狗的特征描述：{voice_description}。\n"
            f"动作姿态严格遵循参考三视图，不生成汉字，背景颜色改为RGB(251,232,207)"
        )

    # Step 5: 调用AI生成图片（使用 requests 直接调用，与 doggenerate 脚本方式一致）
    try:
        import httpx
        from dotenv import load_dotenv
        load_dotenv(override=True)

        ark_url = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        if not ark_url.endswith("/images/generations"):
            ark_url = ark_url.rstrip("/") + "/images/generations"
        ark_key = os.getenv("ARK_API_KEY")
        if not ark_key:
            raise Exception("ARK_API_KEY not set in environment")

        headers = {
            "Authorization": f"Bearer {ark_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "doubao-seedream-5-0-260128",
            "prompt": prompt,
            "size": "2K",
            "response_format": "url",
            "watermark": False,
            "sequential_image_generation": "disabled",
            "image": threeview_b64s
        }
        resp = httpx.post(ark_url, headers=headers, json=payload, timeout=300.0)
        resp.raise_for_status()
        result_data = resp.json()
        image_url = result_data["data"][0]["url"]

        # Step 6: 下载生成的图片并抠背景
        img_response = httpx.get(image_url, timeout=120.0)
        img_response.raise_for_status()
        generated_bytes = img_response.content

        # 抠掉米色背景
        transparent_bytes = _remove_beige_background(generated_bytes)
        result_b64 = base64.b64encode(transparent_bytes).decode()

        return {
            "success": True,
            "message": "图片生成成功",
            "breed_names": breed_names,
            "image_base64": result_b64,
            "threeview_refs": [os.path.basename(p) for p in threeview_paths],
            "prompt_used": prompt
        }

    except httpx.TransportError as e:
        err_msg = str(e)
        is_timeout = any(kw in err_msg.lower() for kw in ["timed out", "timeout", "write operation"])
        return {
            "success": False,
            "message": f"图片生成超时（AI服务响应过慢）: {err_msg}",
            "breed_names": breed_names,
            "image_base64": None,
            "retryable": is_timeout
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "message": f"图片生成请求失败（HTTP {e.response.status_code}）: {str(e)}",
            "breed_names": breed_names,
            "image_base64": None
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"图片生成失败: {str(e)}",
            "breed_names": breed_names,
            "image_base64": None
        }
