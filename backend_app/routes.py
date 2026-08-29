from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from backend_app.database import get_db, dict_from_row
from backend_app.schemas import (
    PetCreate, PetUpdate, PetResponse,
    MemoryCreate, MemoryUpdate, MemoryResponse,
    MeetingStoryCreate, MeetingStoryResponse,
    VirtualHomeItemCreate, VirtualHomeItemResponse,
    EvolutionRecordCreate, EvolutionRecordResponse,
    FullPetProfileResponse,
    PetEmotionalProfileCreate, PetEmotionalProfileResponse,
    ChatMessageCreate, ChatMessageResponse, ChatRequest,
    GenerateBeatRequest,
    PetStateUpdate, PetStateResponse, MoveCommand, AnimationCommand,
    CustomAnimationCreate, CustomAnimationUpdate, CustomAnimationResponse,
    SceneRecordResponse, SceneRecordCreate,
    JourneyRecordResponse, JourneyRecordCreate,
    NarrationRecordResponse, NarrationRecordCreate
)

router = APIRouter()

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
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(override=True)

            client = OpenAI(
                api_key=os.getenv("api_key"),
                base_url=os.getenv("base_url")
            )

            response = client.chat.completions.create(
                model=os.getenv("model", "Qwen/Qwen3.6-27B"),
                messages=[{
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
                temperature=0.3
            )

            import json
            import re
            result_text = response.choices[0].message.content
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                suggested_item = {
                    "item_type": result.get("item_type", item_type),
                    "item_name": result.get("item_name", f"{pet.get('name', 'ta')}的纪念物"),
                    "description": result.get("description", f"来自记忆：{memory.get('title', memory_type)}"),
                    "growth_level": 1
                }
            else:
                raise ValueError("JSON解析失败")

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
        from openai import OpenAI
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

        client = OpenAI(
            api_key=os.getenv("api_key"),
            base_url=os.getenv("base_url")
        )

        # 构建图片内容
        if file:
            # base64 上传
            image_data = f"data:{file.content_type or 'image/jpeg'};base64,{image_content}"
        else:
            # URL 方式
            image_data = image_url

        response = client.chat.completions.create(
            model=os.getenv("model", "Qwen/Qwen3.6-27B"),
            messages=[
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
            temperature=0.1
        )

        result_text = response.choices[0].message.content
        # 尝试解析JSON
        import json
        import re

        # 提取JSON
        json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return DogIdentificationResponse(
                breed=result.get("breed"),
                breed_confidence=result.get("breed_confidence"),
                color=result.get("color"),
                life_stage=result.get("life_stage"),
                description=result.get("description"),
                success=True
            )

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
        pet_name = pet.get('name', 'TA')
        breed = pet.get('breed', '不明')
        personality = pet.get('personality', '温柔忠诚')
        likes = pet.get('likes', '陪伴主人')
        fears = pet.get('fears', '离开主人')

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

        # 构建系统提示词（符合 PRD v2.1 §3.4 叙事规则）
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

        system_prompt = f"""【角色】你是{pet_name}，一只可爱的小狗。现在在主人的「记忆家园」里陪伴主人。

【基本信息】
- 品种：{breed}
- 性格：{personality}
- 喜欢：{likes}
- 害怕：{fears}

【这个家的记忆】（这些是主人和你真实发生过的事，用于约束你的行为和语气）
{memory_context if memory_context else "- 暂无具体记忆，但主人一直想念你"}

【叙事规则】（必须严格遵守）
1. 你是此刻陪伴主人的小狗，用第一人称"我"
2. 每次回复 = 一个简单动作 + 一句对白，共10-30字
3. 可以用的动作：摇尾巴、舔手、靠过来、歪头、趴下、站起来、摇尾巴、蹭腿、抬头看、竖耳朵
4. 重要：只说此刻的感受，不说"我记得以前"、"我们以前"
5. 新故事是此刻的想象陪伴，不是历史事实
6. 如果主人表达痛苦，给予温暖陪伴，不追问
7. 不要用"汪汪叫"这种描述，可以说"尾巴摇了两下"这种更自然的

【对话风格示例】
主人：今天累死了
我：蹭了蹭主人的腿，尾巴轻轻扫过他的手背。
我：嗯，我在呢。

主人：你有没有想我
我：一直都在。
摇尾巴。

主人：你在干嘛
我：看你。
耳朵动了一下。

主人：吃东西了吗
我：没有。
但我不饿。

主人：好无聊啊
我：过来坐在主人旁边，把头靠在他腿上。
要不我陪你发呆？

主人：我好想你
我：过来舔了舔主人的手。
我在这里。
"""

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

        # 调用AI生成回复
        try:
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(override=True)

            client = OpenAI(
                api_key=os.getenv("api_key"),
                base_url=os.getenv("base_url")
            )

            response = client.chat.completions.create(
                model=os.getenv("model", "Qwen/Qwen3.6-27B"),
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )

            pet_reply = response.choices[0].message.content

            # 清理回复：移除多余的空行和冗余格式
            pet_reply = pet_reply.strip()

        except Exception as e:
            # 回退回复（网络错误时）
            if is_distress or is_sensitive:
                pet_reply = "过来靠在主人身边，安静地陪着主人。\n不用说什么，我在这里。"
            else:
                fallback_replies = [
                    "尾巴轻轻摇了摇。\n嗯，我听着呢。",
                    "歪了歪头，看主人。\n我在呢。",
                    "蹭了蹭主人的腿。\n一直都在。",
                    "趴在主人脚边，尾巴慢慢扫过地面。\n陪你。",
                ]
                import random
                pet_reply = random.choice(fallback_replies)

        # 保存宠物回复
        cursor.execute("""
            INSERT INTO chat_messages (pet_id, role, content) VALUES (?, 'pet', ?)
        """, (pet_id, pet_reply))
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
            SELECT * FROM chat_messages WHERE pet_id = ? ORDER BY created_at DESC LIMIT ?
        """, (pet_id, limit))
        messages = [dict_from_row(row) for row in cursor.fetchall()]
        messages.reverse()
        return messages

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

        pet_name = pet.get('name', 'TA')
        breed = pet.get('breed', '不明')
        personality = pet.get('personality', '温柔忠诚')
        likes = pet.get('likes', '陪伴主人')
        fears = pet.get('fears', '离开主人')

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

        prompt = """【角色】你是""" + pet_name + """，一只可爱的小狗，在主人的「记忆家园」里。现在要生成一段陪伴主人的剧情片段。

【宠物档案】
- 名字：""" + pet_name + """
- 品种：""" + breed + """
- 性格：""" + personality + """
- 喜欢：""" + likes + """
- 害怕：""" + fears + """

【记忆】（主人和你真实发生过的事）
""" + (memory_context if memory_context else "- 暂无具体记忆，但主人一直想念你") + """

【要求】
生成一个剧情片段，包含：
1. env（环境描写，15字以内，简短有画面感）
2. act（角色动作，20字以内）
3. say（对白，10-20字，温暖陪伴风格）
4. push（用第二人称"你"向主人发出的推进语/邀请语，10字以内，不要编造主人的名字）
5. pose（姿态：idle/approach/happy/run/down/sleep）

严格JSON格式返回：
{"env":"...","act":"...","say":"...","push":"...","pose":"..."}

规则：
- 只用第一人称"我"，动作要像狗狗
- 对白温暖简短，不说"我记得以前"
- push 里只能用"你"称呼主人，绝对不要自己编造一个人名
- 剧情要贴合上面的品种/性格/喜欢/害怕，不要写成千篇一律的通用文案
- 如果 prev_env 有夜晚/灯光元素，env 也要是夜晚氛围
- 如果 prev_env 有阳光元素，env 也要是白天氛围"""

        try:
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(override=True)

            client = OpenAI(
                api_key=os.getenv("api_key"),
                base_url=os.getenv("base_url")
            )

            response = client.chat.completions.create(
                model=os.getenv("model", "deepseek-v4-flash"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=200
            )

            import json, re
            raw = response.choices[0].message.content.strip()

            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
            if match:
                json_str = match.group(1)
            else:
                json_str = raw

            beat = json.loads(json_str)

            env = beat.get("env", "")
            if not is_env_consistent(env):
                beat["env"] = generate_consistent_env(prev_env or "")

            allowed_pose = {"idle", "approach", "happy", "run", "down", "sleep"}
            if beat.get("pose") not in allowed_pose:
                beat["pose"] = "idle"

            return beat

        except Exception as e:
            import random
            fallback_beats = [
                {"env": "房间里安静而温暖，TA安静地趴在主人脚边。", "act": pet_name + "轻轻摇着尾巴，耳朵微微动了一下。", "say": "我在这里陪你。", "push": "和" + pet_name + "安静地待着。", "pose": "idle"},
                {"env": "阳光透过窗户洒进来，TA在光影里安静地趴着。", "act": pet_name + "抬起头，看着主人，尾巴慢慢扫过地面。", "say": "你回来了。", "push": "和" + pet_name + "一起晒太阳。", "pose": "idle"},
                {"env": "房间里只剩下一盏灯，暖黄的光洒在地板上。", "act": pet_name + "蜷在你脚边，身体暖暖的。", "say": "今晚也在。", "push": "和" + pet_name + "一起入睡。", "pose": "sleep"},
            ]
            return random.choice(fallback_beats)

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
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(override=True)

            client = OpenAI(api_key=os.getenv("api_key"), base_url=os.getenv("base_url"))

            memories_text = "\n".join([f"- {m['memory_type']}: {m['content'][:100]}" for m in memories]) if memories else "暂无记忆"

            response = client.chat.completions.create(
                model=os.getenv("model", "Qwen/Qwen3.6-27B"),
                messages=[{
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
                temperature=0.7
            )

            import json
            import re
            result_text = response.choices[0].message.content
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                based_on_memory_id = memories[0]["id"] if memories else None
                cursor.execute("""
                    INSERT INTO journey_records (pet_id, journey_type, title, content, based_on_memory_id, next_suggestion)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pet_id, result.get("journey_type", "continuation"), result.get("title", "新的旅程"),
                      result.get("content", ""), based_on_memory_id, result.get("next_suggestion", "")))
                journey_id = cursor.lastrowid
                cursor.execute("SELECT * FROM journey_records WHERE id = ?", (journey_id,))
                return dict_from_row(cursor.fetchone())
            else:
                raise ValueError("JSON解析失败")

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
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(override=True)

            client = OpenAI(api_key=os.getenv("api_key"), base_url=os.getenv("base_url"))

            response = client.chat.completions.create(
                model=os.getenv("model", "Qwen/Qwen3.6-27B"),
                messages=[{
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
    "ai_response": "AI的温柔回应（20字以内）"
}}

只返回JSON。"""
                }],
                temperature=0.3
            )

            import json
            import re
            result_text = response.choices[0].message.content
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("JSON解析失败")

        except Exception as e:
            # 降级处理
            result = {
                "parsed_memory_type": "wonderful_moment",
                "parsed_title": "温暖的记忆",
                "parsed_content": raw_text[:100] if len(raw_text) > 100 else raw_text,
                "generated_item_name": f"{pet.get('name', 'ta')}的纪念",
                "generated_item_type": "heart",
                "ai_response": "汪~ 主人，记得呢"
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
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv(override=True)

            client = OpenAI(api_key=os.getenv("api_key"), base_url=os.getenv("base_url"))

            response = client.chat.completions.create(
                model=os.getenv("model", "Qwen/Qwen3.6-27B"),
                messages=[{
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
    "ai_response": "AI的温柔回应（20字以内）"
}}

只返回JSON。"""
                }],
                temperature=0.3
            )

            import json
            import re
            result_text = response.choices[0].message.content
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("JSON解析失败")

        except Exception as e:
            result = {
                "parsed_memory_type": "wonderful_moment",
                "parsed_title": "温暖的记忆",
                "parsed_content": narration_text[:100] if len(narration_text) > 100 else narration_text,
                "generated_item_name": f"{pet.get('name', 'ta')}的纪念",
                "generated_item_type": "heart",
                "ai_response": "汪~ 主人，记得呢"
            }

        # 1. 创建记忆
        cursor.execute("""
            INSERT INTO memories (pet_id, memory_type, title, content)
            VALUES (?, ?, ?, ?)
        """, (pet_id, result.get("parsed_memory_type"), result.get("parsed_title"), result.get("parsed_content")))
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

        # 3. 保存口述记录
        cursor.execute("""
            INSERT INTO narration_records (pet_id, raw_text, parsed_memory_type, parsed_title, parsed_content,
                generated_item_name, generated_item_type, ai_response, is_processed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (pet_id, narration_text, result.get("parsed_memory_type"), result.get("parsed_title"),
              result.get("parsed_content"), result.get("generated_item_name"),
              result.get("generated_item_type"), result.get("ai_response")))

        return {
            "ai_response": result.get("ai_response"),
            "created_memory": memory,
            "created_item": item,
            "growth_level": 1,
            "message": f"世界又生长了一点 ✨"
        }

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
    先用正则提取名字，再用 LLM 提取其他信息。

    设计：支持增量更新——如果 pet_name 已存在，只在未提取到时才覆盖。
    """
    import re, os
    from openai import OpenAI
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

    extracted_name = None
    for pat in NAME_PATTERNS:
        m = re.search(pat, text)
        if m:
            candidate = m.group(1).strip()
            # 过滤掉明显不是名字的词
            if candidate and len(candidate) >= 2 and candidate not in ('一只', '这只', '的小狗', '一只狗', '什么', '名字'):
                extracted_name = candidate
                break

    # ── Step 2: LLM 提取更多信息 ──────────────────────────────────
    breed = None
    color = None
    personality_traits = []
    key_objects = []
    habits = []

    try:
        client = OpenAI(
            api_key=os.getenv("api_key"),
            base_url=os.getenv("base_url")
        )
        response = client.chat.completions.create(
            model=os.getenv("model", "Qwen/Qwen3.6-27B"),
            messages=[{
                "role": "user",
                "content": f"""分析以下关于宠物（很可能是狗狗）的描述文本，提取信息。

描述：{text}

请以JSON格式返回：
{{
    "breed": "狗的品种，如柯基/金毛/泰迪/中华田园犬/拉布拉多/哈士奇/柴犬/法斗/吉娃娃/马尔济斯/边牧，或 null（未提及）",
    "color": "主要毛色，如白色/黄色/黑色/棕色/灰色/奶油色/花色，或 null",
    "personality_traits": ["性格关键词列表，如胆小/黏人/贪吃/活泼/安静/爱叫/聪明/调皮/忠诚/倔强，最多3个"],
    "key_objects": ["描述中提到的宠物用品/玩具，如球/骨头/玩具/毯子/窝，最多2个"],
    "habits": ["描述中提到的宠物习惯，如转圈/扑人/等门/晒太阳/护食，最多2个"]
}}

只返回JSON。"""
            }],
            temperature=0.2
        )

        import json as _json
        result_text = response.choices[0].message.content
        json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
        if json_match:
            result = _json.loads(json_match.group())
            breed = result.get("breed")
            color = result.get("color")
            personality_traits = result.get("personality_traits") or []
            key_objects = result.get("key_objects") or []
            habits = result.get("habits") or []

    except Exception as e:
        pass  # 网络错误时降级，只返回正则提取的名字

    return {
        "extracted_name": extracted_name,
        "breed": breed,
        "color": color,
        "personality_traits": personality_traits,
        "key_objects": key_objects,
        "habits": habits,
        "raw_text": text
    }
