# Navigation System Redesign - Implementation Plan
# 导航系统重新设计 - 实施计划

**Task ID**: 04-03-page-awareness-navigation-v2-redesign
**Created**: 2026-04-03
**Status**: Planning
**Priority**: 🔴 P0 - Critical

---

## 问题总结 / Problem Summary

当前导航系统存在严重缺陷：
1. ❌ AI 不理解菜单语义（只有标题，无描述）
2. ❌ 基于关键词匹配，无法处理变体和同义词
3. ❌ 从非 dashboard 页面无法导航（如从组织管理页面）
4. ❌ 没有 LLM 回退，无法处理模糊情况

**根本原因**：整个系统基于关键词匹配，缺乏语义理解。

---

## 重构目标 / Redesign Goals

### 核心目标
1. ✅ AI 能从任何页面导航到任何页面
2. ✅ 理解自然语言变体（"添加智能体" = "创建 agent" = "新增 AI 助手"）
3. ✅ 支持跨语言（中英文混用）
4. ✅ 处理歧义情况（多个匹配时询问用户）

### 性能目标
- 意图检测：< 500ms
- 菜单匹配：< 300ms
- 端到端导航：< 2s

### 准确率目标
- 意图检测：95%+
- 菜单匹配：90%+

---

## 实施计划 / Implementation Plan

### Phase 1: 菜单元数据增强（第 1 周）

#### Task 1.1: 定义扩展接口
**文件**: `frontend/apps/web-antd/src/utils/menu-navigation.ts`

**修改**:
```typescript
export interface MenuNavigationEntry {
  breadcrumb: string[];
  endpoint: string;
  path: string;
  pageKey: string;
  title: string;
  
  // NEW: Semantic metadata
  description?: string;      // 页面功能描述
  keywords?: string[];       // 搜索关键词（含同义词）
  capabilities?: string[];   // 可用操作
  category?: string;         // 页面分类
}
```

#### Task 1.2: 为所有路由添加元数据
**文件**: 
- `frontend/apps/web-antd/src/router/routes/admin/index.ts`
- `frontend/apps/web-antd/src/router/routes/tenant/index.ts`

**示例**:
```typescript
{
  name: 'AdminAIAgents',
  path: 'ai/agents',
  component: () => import('#/views/admin/ai/agents/index.vue'),
  meta: {
    icon: 'lucide:bot',
    title: 'admin.ai.agent.title',
    ai: {
      mode: 'operate',
      // NEW metadata
      description: '创建、编辑和管理 AI 智能体，配置智能体的能力和行为',
      keywords: ['智能体', 'agent', 'AI助手', '机器人', '创建智能体', '编辑智能体'],
      capabilities: ['create_agent', 'edit_agent', 'delete_agent', 'view_agents'],
      category: 'ai'
    }
  },
}
```

**需要添加元数据的页面**（优先级排序）:
1. `/admin/ai/agents` - 智能体管理
2. `/admin/ai/knowledge-bases` - 知识库
3. `/admin/plugins` - 插件管理
4. `/admin/system/organization` - 组织管理
5. `/admin/system/users` - 用户管理
6. `/admin/system/roles` - 角色管理
7. `/admin/system/settings` - 系统设置
8. `/tenant/ai/agents` - 企业端智能体
9. `/tenant/ai/knowledge-bases` - 企业端知识库
10. 其他所有菜单页面

#### Task 1.3: 更新菜单构建逻辑
**文件**: `frontend/apps/web-antd/src/utils/menu-navigation.ts`

**修改**: `buildMenuNavigationEntries` 函数提取新增的元数据

```typescript
function buildMenuNavigationEntries(options): MenuNavigationEntry[] {
  // ... existing code ...
  
  const entry: MenuNavigationEntry = {
    // ... existing fields ...
    description: metaAi?.description,
    keywords: metaAi?.keywords || [],
    capabilities: metaAi?.capabilities || [],
    category: metaAi?.category,
  };
  
  return entry;
}
```

#### Task 1.4: 测试元数据完整性
**文件**: `frontend/apps/web-antd/src/utils/__tests__/menu-navigation.test.ts`

**新增测试**:
```typescript
describe('Menu metadata completeness', () => {
  it('should have description for all major pages', () => {
    const entries = buildMenuNavigationEntries({...});
    const majorPages = entries.filter(e => e.category === 'ai' || e.category === 'system');
    
    for (const page of majorPages) {
      expect(page.description).toBeDefined();
      expect(page.keywords).toHaveLength.greaterThan(0);
    }
  });
});
```

**验收标准**:
- ✅ 所有主要页面有 description
- ✅ 所有主要页面有至少 3 个 keywords
- ✅ 测试通过

---

### Phase 2: LLM 意图检测（第 2 周）

#### Task 2.1: 创建意图分类服务
**文件**: `backend/app/ai/services/navigation_intent_classifier.py` (NEW)

**实现**:
```python
from app.ai.gateway import AIGateway
from app.ai.types import ChatMessage

class NavigationIntentClassifier:
    """LLM-based navigation intent detection"""
    
    def __init__(self, gateway: AIGateway):
        self.gateway = gateway
        self.cache = {}  # Simple in-memory cache
    
    async def detect(
        self,
        user_text: str,
        current_page: dict,
        available_menus: list[dict]
    ) -> dict:
        """
        Detect if user wants to navigate
        
        Returns:
            {
                "needs_navigation": bool,
                "target_description": str | None,
                "confidence": float,
                "reason": str
            }
        """
        # Fast path: obvious keywords
        if self._quick_check(user_text):
            return {
                "needs_navigation": True,
                "target_description": self._extract_target(user_text),
                "confidence": 0.9,
                "reason": "keyword_match"
            }
        
        # LLM classification
        return await self._llm_classify(user_text, current_page, available_menus)
    
    def _quick_check(self, text: str) -> bool:
        """Fast keyword check for obvious cases"""
        nav_keywords = ["添加", "创建", "新增", "打开", "进入", "跳转", "切到", "前往", "管理"]
        return any(kw in text for kw in nav_keywords)
    
    def _extract_target(self, text: str) -> str | None:
        """Extract target from text"""
        # Simple extraction for fast path
        targets = ["智能体", "知识库", "插件", "用户", "角色", "组织"]
        for target in targets:
            if target in text:
                return target
        return None
    
    async def _llm_classify(
        self,
        user_text: str,
        current_page: dict,
        available_menus: list[dict]
    ) -> dict:
        """Use LLM for classification"""
        prompt = self._build_classification_prompt(user_text, current_page, available_menus)
        
        messages = [
            ChatMessage(role="system", content="You are a navigation intent classifier."),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = await self.gateway.chat(
            messages=messages,
            model="fast",  # Use fast model
            temperature=0.0,
            max_tokens=200
        )
        
        # Parse JSON response
        import json
        result = json.loads(response.content)
        return result
    
    def _build_classification_prompt(
        self,
        user_text: str,
        current_page: dict,
        available_menus: list[dict]
    ) -> str:
        """Build prompt for LLM classification"""
        menu_list = "\n".join([
            f"- {m['title']}: {m.get('description', 'N/A')}"
            for m in available_menus[:20]  # Limit to top 20
        ])
        
        return f"""
User is currently on page: {current_page.get('title', 'Unknown')}
User says: "{user_text}"

Available pages in this system:
{menu_list}

Question: Does the user want to navigate to a different page?

If yes, what is the user trying to do? (Describe in a few words)

Return JSON:
{{
  "needs_navigation": true or false,
  "target_description": "what user wants to do" or null,
  "confidence": 0.0 to 1.0,
  "reason": "brief explanation"
}}

Examples:
- "我想添加一个智能体" → {{"needs_navigation": true, "target_description": "创建智能体", "confidence": 0.95}}
- "这个页面是干什么的" → {{"needs_navigation": false, "target_description": null, "confidence": 0.9}}
"""
```

#### Task 2.2: 集成到 Planner
**文件**: `backend/app/ai/engine/tool_invocation_planner.py`

**修改**: 在 `_is_explicit_page_request` 中添加 LLM 回退

```python
@classmethod
async def _is_explicit_page_request_with_llm(
    cls,
    user_text: str,
    *,
    page_context_present: bool,
    input_variables: dict[str, Any] | None = None,
    intent_classifier: NavigationIntentClassifier | None = None
) -> bool:
    # Try pattern matching first (fast path)
    if cls._is_explicit_page_request(user_text, page_context_present=page_context_present, input_variables=input_variables):
        return True
    
    # Fallback to LLM if available
    if intent_classifier and page_context_present:
        page_context = input_variables.get(PAGE_CONTEXT_KEY) if isinstance(input_variables, dict) else None
        if page_context:
            result = await intent_classifier.detect(
                user_text,
                current_page=page_context,
                available_menus=[]  # TODO: Pass available menus
            )
            return result.get("needs_navigation", False) and result.get("confidence", 0) > 0.7
    
    return False
```

#### Task 2.3: 测试意图检测
**文件**: `backend/tests/ai/test_navigation_intent_classifier.py` (NEW)

**测试用例**:
```python
@pytest.mark.asyncio
async def test_detect_navigation_intent_obvious():
    classifier = NavigationIntentClassifier(gateway)
    result = await classifier.detect(
        "我想添加一个智能体",
        current_page={"title": "组织管理"},
        available_menus=[...]
    )
    assert result["needs_navigation"] is True
    assert result["confidence"] > 0.8

@pytest.mark.asyncio
async def test_detect_navigation_intent_synonym():
    classifier = NavigationIntentClassifier(gateway)
    result = await classifier.detect(
        "创建一个 agent",
        current_page={"title": "组织管理"},
        available_menus=[...]
    )
    assert result["needs_navigation"] is True

@pytest.mark.asyncio
async def test_detect_no_navigation_intent():
    classifier = NavigationIntentClassifier(gateway)
    result = await classifier.detect(
        "这个页面是干什么的",
        current_page={"title": "组织管理"},
        available_menus=[...]
    )
    assert result["needs_navigation"] is False
```

**验收标准**:
- ✅ 测试通过率 > 95%
- ✅ 快速路径 < 10ms
- ✅ LLM 路径 < 500ms

---

### Phase 3: LLM 菜单匹配（第 2-3 周）

#### Task 3.1: 创建菜单匹配服务
**文件**: `backend/app/ai/services/menu_matcher.py` (NEW)

**实现**:
```python
class MenuMatcher:
    """LLM-based semantic menu matching"""
    
    async def match(
        self,
        user_target: str,
        available_menus: list[dict],
        context: dict
    ) -> dict:
        """
        Find best matching menu
        
        Returns:
            {
                "best_match": dict | None,
                "confidence": float,
                "alternatives": list[dict],
                "reason": str
            }
        """
        # Check cache
        cache_key = f"{user_target}:{context.get('current_page')}"
        if cached := self.cache.get(cache_key):
            return cached
        
        # LLM matching
        result = await self._llm_match(user_target, available_menus, context)
        self.cache.set(cache_key, result, ttl=300)  # 5 min cache
        return result
    
    async def _llm_match(
        self,
        user_target: str,
        available_menus: list[dict],
        context: dict
    ) -> dict:
        """Use LLM for semantic matching"""
        prompt = self._build_matching_prompt(user_target, available_menus, context)
        
        messages = [
            ChatMessage(role="system", content="You are a menu matching assistant."),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = await self.gateway.chat(
            messages=messages,
            model="fast",
            temperature=0.0,
            max_tokens=300
        )
        
        import json
        result = json.loads(response.content)
        
        # Resolve page_key to actual menu entry
        best_match = next(
            (m for m in available_menus if m["pageKey"] == result.get("best_match_key")),
            None
        )
        
        return {
            "best_match": best_match,
            "confidence": result.get("confidence", 0),
            "alternatives": [
                m for m in available_menus 
                if m["pageKey"] in result.get("alternative_keys", [])
            ],
            "reason": result.get("reason", "")
        }
    
    def _build_matching_prompt(
        self,
        user_target: str,
        available_menus: list[dict],
        context: dict
    ) -> str:
        """Build prompt for menu matching"""
        menu_list = "\n".join([
            f"- {m['pageKey']}: {m['title']} - {m.get('description', 'N/A')}\n  Keywords: {', '.join(m.get('keywords', []))}"
            for m in available_menus
        ])
        
        return f"""
User wants to: "{user_target}"
Current page: {context.get('current_page', 'Unknown')}

Available pages:
{menu_list}

Question: Which page best matches what the user wants to do?

Consider:
1. Semantic meaning (not just keywords)
2. User's intent (what they want to accomplish)
3. Page descriptions and capabilities

Return JSON:
{{
  "best_match_key": "page_key",
  "confidence": 0.0 to 1.0,
  "alternative_keys": ["page_key1", "page_key2"],
  "reason": "brief explanation"
}}

If no good match, return:
{{
  "best_match_key": null,
  "confidence": 0.0,
  "alternative_keys": [],
  "reason": "no suitable page found"
}}
"""
```

#### Task 3.2: 集成到导航操作
**文件**: `backend/app/ai/tools/executors/page_operation_executor.py`

**修改**: 在处理 `navigate_menu` 时使用 LLM 匹配

```python
# In navigate_menu handler
if operation_name == "navigate_menu":
    target = params.get("target", "")
    
    # Get available menus from page context
    available_menus = self._extract_available_menus(context)
    
    # Use LLM matcher
    matcher = MenuMatcher(self.gateway)
    match_result = await matcher.match(
        user_target=target,
        available_menus=available_menus,
        context={"current_page": context.page_key}
    )
    
    if match_result["confidence"] < 0.7:
        # Low confidence, return alternatives
        return {
            "success": False,
            "message": f"找到多个可能的页面，请明确指定：",
            "data": {
                "alternatives": match_result["alternatives"]
            }
        }
    
    # Navigate to best match
    best_match = match_result["best_match"]
    # ... continue with navigation
```

#### Task 3.3: 测试菜单匹配
**文件**: `backend/tests/ai/test_menu_matcher.py` (NEW)

**测试用例**:
```python
@pytest.mark.asyncio
async def test_match_exact():
    matcher = MenuMatcher(gateway)
    result = await matcher.match(
        "智能体管理",
        available_menus=[...],
        context={}
    )
    assert result["best_match"]["pageKey"] == "admin.ai.agents"
    assert result["confidence"] > 0.9

@pytest.mark.asyncio
async def test_match_synonym():
    matcher = MenuMatcher(gateway)
    result = await matcher.match(
        "创建 agent",
        available_menus=[...],
        context={}
    )
    assert result["best_match"]["pageKey"] == "admin.ai.agents"

@pytest.mark.asyncio
async def test_match_ambiguous():
    matcher = MenuMatcher(gateway)
    result = await matcher.match(
        "设置",
        available_menus=[...],
        context={}
    )
    assert result["confidence"] < 0.7
    assert len(result["alternatives"]) > 1
```

**验收标准**:
- ✅ 测试通过率 > 90%
- ✅ 匹配时间 < 300ms (with cache)
- ✅ 缓存命中率 > 80%

---

### Phase 4: 集成和验证（第 3-4 周）

#### Task 4.1: 端到端集成测试
**测试场景**:

1. **从组织管理页面导航到智能体**
   - 输入: "我想添加一个智能体"
   - 当前页: `/admin/system/organization`
   - 预期: 导航到 `/admin/ai/agents`，打开创建表单

2. **同义词匹配**
   - 输入: "创建一个 agent"
   - 预期: 导航到智能体页面

3. **跨语言**
   - 输入: "open knowledge base"
   - 预期: 导航到知识库页面

4. **歧义处理**
   - 输入: "打开设置"
   - 预期: 询问用户（系统设置 vs 智能体设置 vs 插件设置）

5. **上下文感知**
   - 当前页: 智能体页面
   - 输入: "我想添加一个智能体"
   - 预期: 直接打开创建表单（不导航）

#### Task 4.2: 性能优化
- ✅ 添加缓存层
- ✅ 优化 LLM prompt 长度
- ✅ 使用更快的模型
- ✅ 并行处理意图检测和菜单匹配

#### Task 4.3: MCP 验证
- ✅ 在真实环境测试所有场景
- ✅ 记录失败案例
- ✅ 调整 prompt 和阈值

---

## 风险和缓解 / Risks and Mitigation

### Risk 1: LLM 调用延迟
**缓解**: 
- 快速路径处理常见情况
- 缓存常见查询
- 使用快速模型

### Risk 2: LLM 成本
**缓解**:
- 缓存减少调用次数
- 快速路径减少 LLM 使用
- 使用小模型

### Risk 3: 准确率不达标
**缓解**:
- 迭代优化 prompt
- 收集失败案例
- 调整置信度阈值

---

## 验收标准 / Acceptance Criteria

### 功能验收
- ✅ 从任何页面都能导航到目标页面
- ✅ 支持自然语言变体和同义词
- ✅ 处理歧义情况（询问用户）
- ✅ 跨语言支持（中英文）

### 性能验收
- ✅ 意图检测 < 500ms
- ✅ 菜单匹配 < 300ms
- ✅ 端到端导航 < 2s

### 准确率验收
- ✅ 意图检测准确率 > 95%
- ✅ 菜单匹配准确率 > 90%
- ✅ 端到端成功率 > 85%

---

## 时间估算 / Time Estimate

- Phase 1: 5 天
- Phase 2: 5 天
- Phase 3: 5 天
- Phase 4: 5 天
- **总计**: 20 天（4 周）

---

## 下一步 / Next Steps

1. ✅ 审查此计划
2. ✅ 批准重构方案
3. ✅ 开始 Phase 1: 添加菜单元数据
4. ✅ 并行开发 LLM 服务
5. ✅ 集成和测试

---

**结论**: 当前导航系统需要完全重构。使用 LLM 进行语义理解是唯一可行的解决方案。预计 4 周完成。
