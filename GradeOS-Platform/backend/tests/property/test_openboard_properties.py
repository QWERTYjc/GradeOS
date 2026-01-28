"""
OpenBoard 论坛系统 Property-Based Tests

使用 Hypothesis 进行属性测试，验证系统的正确性属性。

Feature: openboard-forum
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
from typing import List, Optional
from enum import Enum


# ==================== 数据生成策略 ====================

class ForumStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"


# 论坛名称策略：1-100 字符的非空字符串
forum_name_strategy = st.text(min_size=1, max_size=100).filter(lambda x: x.strip())

# 论坛描述策略：0-500 字符
forum_description_strategy = st.text(min_size=0, max_size=500)

# 用户 ID 策略
user_id_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N')))

# 帖子标题策略：1-200 字符
post_title_strategy = st.text(min_size=1, max_size=200).filter(lambda x: x.strip())

# 帖子内容策略：1-10000 字符
post_content_strategy = st.text(min_size=1, max_size=10000).filter(lambda x: x.strip())

# 回复内容策略：1-5000 字符
reply_content_strategy = st.text(min_size=1, max_size=5000).filter(lambda x: x.strip())


# 论坛数据策略
@st.composite
def forum_strategy(draw):
    return {
        "forum_id": f"forum_{draw(st.text(min_size=8, max_size=12, alphabet='abcdef0123456789'))}",
        "name": draw(forum_name_strategy),
        "description": draw(forum_description_strategy),
        "creator_id": draw(user_id_strategy),
        "status": ForumStatus.PENDING,  # 新创建的论坛总是 pending
        "post_count": 0,
        "created_at": datetime.now(),
    }


# 帖子数据策略
@st.composite
def post_strategy(draw, forum_id: str = None):
    return {
        "post_id": f"post_{draw(st.text(min_size=8, max_size=12, alphabet='abcdef0123456789'))}",
        "forum_id": forum_id or f"forum_{draw(st.text(min_size=8, max_size=12, alphabet='abcdef0123456789'))}",
        "title": draw(post_title_strategy),
        "content": draw(post_content_strategy),
        "author_id": draw(user_id_strategy),
        "reply_count": 0,
        "is_deleted": False,
        "created_at": datetime.now(),
    }


# 回复数据策略
@st.composite
def reply_strategy(draw, post_id: str = None):
    return {
        "reply_id": f"reply_{draw(st.text(min_size=8, max_size=12, alphabet='abcdef0123456789'))}",
        "post_id": post_id or f"post_{draw(st.text(min_size=8, max_size=12, alphabet='abcdef0123456789'))}",
        "content": draw(reply_content_strategy),
        "author_id": draw(user_id_strategy),
        "is_deleted": False,
        "created_at": datetime.now(),
    }


# ==================== 模拟数据存储 ====================

class MockForumStore:
    """模拟论坛数据存储，用于属性测试"""
    
    def __init__(self):
        self.forums = {}
        self.posts = {}
        self.replies = {}
        self.banned_users = set()
    
    def create_forum(self, forum_data: dict) -> dict:
        """创建论坛（状态为 pending）"""
        forum_data["status"] = ForumStatus.PENDING
        forum_data["post_count"] = 0
        self.forums[forum_data["forum_id"]] = forum_data
        return forum_data
    
    def approve_forum(self, forum_id: str, approved: bool) -> dict:
        """审核论坛"""
        if forum_id not in self.forums:
            raise ValueError("Forum not found")
        
        forum = self.forums[forum_id]
        if forum["status"] != ForumStatus.PENDING:
            raise ValueError("Forum already reviewed")
        
        forum["status"] = ForumStatus.ACTIVE if approved else ForumStatus.REJECTED
        return forum
    
    def create_post(self, post_data: dict) -> dict:
        """创建帖子"""
        forum_id = post_data["forum_id"]
        author_id = post_data["author_id"]
        
        if author_id in self.banned_users:
            raise ValueError("User is banned")
        
        if forum_id not in self.forums:
            raise ValueError("Forum not found")
        
        if self.forums[forum_id]["status"] != ForumStatus.ACTIVE:
            raise ValueError("Forum not active")
        
        post_data["reply_count"] = 0
        self.posts[post_data["post_id"]] = post_data
        self.forums[forum_id]["post_count"] += 1
        return post_data
    
    def create_reply(self, reply_data: dict) -> dict:
        """创建回复"""
        post_id = reply_data["post_id"]
        author_id = reply_data["author_id"]
        
        if author_id in self.banned_users:
            raise ValueError("User is banned")
        
        if post_id not in self.posts:
            raise ValueError("Post not found")
        
        if self.posts[post_id]["is_deleted"]:
            raise ValueError("Post is deleted")
        
        self.replies[reply_data["reply_id"]] = reply_data
        self.posts[post_id]["reply_count"] += 1
        return reply_data
    
    def get_post_replies(self, post_id: str) -> List[dict]:
        """获取帖子回复（按时间正序）"""
        replies = [r for r in self.replies.values() if r["post_id"] == post_id and not r["is_deleted"]]
        return sorted(replies, key=lambda x: x["created_at"])
    
    def ban_user(self, user_id: str):
        """封禁用户"""
        self.banned_users.add(user_id)
    
    def unban_user(self, user_id: str):
        """解封用户"""
        self.banned_users.discard(user_id)
    
    def search_posts(self, keyword: str, forum_id: Optional[str] = None) -> List[dict]:
        """搜索帖子"""
        results = []
        for post in self.posts.values():
            if post["is_deleted"]:
                continue
            
            # 检查论坛是否激活
            if post["forum_id"] not in self.forums:
                continue
            if self.forums[post["forum_id"]]["status"] != ForumStatus.ACTIVE:
                continue
            
            # 按论坛筛选
            if forum_id and post["forum_id"] != forum_id:
                continue
            
            # 关键词匹配
            if keyword.lower() in post["title"].lower() or keyword.lower() in post["content"].lower():
                results.append(post)
        
        return results


# ==================== Property Tests ====================

class TestForumStatusTransitions:
    """
    Property 1: Forum Status Transitions
    
    *For any* forum creation request, the initial status SHALL be 'pending',
    and only teacher approval/rejection SHALL change the status to 'active' or 'rejected'.
    
    **Validates: Requirements 1.1, 1.2, 1.3**
    """
    
    @given(forum_strategy())
    @settings(max_examples=100)
    def test_new_forum_always_pending(self, forum_data):
        """
        Feature: openboard-forum, Property 1: Forum Status Transitions
        新创建的论坛状态必须是 pending
        """
        store = MockForumStore()
        created = store.create_forum(forum_data)
        
        assert created["status"] == ForumStatus.PENDING
    
    @given(forum_strategy(), st.booleans())
    @settings(max_examples=100)
    def test_approval_changes_status_correctly(self, forum_data, approved):
        """
        Feature: openboard-forum, Property 1: Forum Status Transitions
        审核操作正确改变论坛状态
        """
        store = MockForumStore()
        store.create_forum(forum_data)
        
        result = store.approve_forum(forum_data["forum_id"], approved)
        
        expected_status = ForumStatus.ACTIVE if approved else ForumStatus.REJECTED
        assert result["status"] == expected_status
    
    @given(forum_strategy(), st.booleans())
    @settings(max_examples=100)
    def test_cannot_approve_twice(self, forum_data, approved):
        """
        Feature: openboard-forum, Property 1: Forum Status Transitions
        已审核的论坛不能再次审核
        """
        store = MockForumStore()
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], approved)
        
        with pytest.raises(ValueError, match="already reviewed"):
            store.approve_forum(forum_data["forum_id"], not approved)


class TestReplyCountConsistency:
    """
    Property 3: Reply Count Consistency
    
    *For any* reply added to a post, the post's reply_count SHALL increment by exactly 1,
    and replies SHALL be returned in chronological order.
    
    **Validates: Requirements 3.1, 3.2, 3.3**
    """
    
    @given(forum_strategy(), post_strategy(), st.lists(reply_strategy(), min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_reply_count_increments_correctly(self, forum_data, post_data, replies_data):
        """
        Feature: openboard-forum, Property 3: Reply Count Consistency
        每添加一个回复，reply_count 增加 1
        """
        store = MockForumStore()
        
        # 创建并激活论坛
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], True)
        
        # 创建帖子
        post_data["forum_id"] = forum_data["forum_id"]
        store.create_post(post_data)
        
        # 添加回复并验证计数
        for i, reply_data in enumerate(replies_data):
            reply_data["post_id"] = post_data["post_id"]
            reply_data["reply_id"] = f"reply_{i}_{reply_data['reply_id']}"  # 确保唯一
            store.create_reply(reply_data)
            
            assert store.posts[post_data["post_id"]]["reply_count"] == i + 1
    
    @given(forum_strategy(), post_strategy(), st.lists(reply_strategy(), min_size=2, max_size=10))
    @settings(max_examples=100)
    def test_replies_in_chronological_order(self, forum_data, post_data, replies_data):
        """
        Feature: openboard-forum, Property 3: Reply Count Consistency
        回复按时间正序返回
        """
        store = MockForumStore()
        
        # 创建并激活论坛
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], True)
        
        # 创建帖子
        post_data["forum_id"] = forum_data["forum_id"]
        store.create_post(post_data)
        
        # 添加回复
        for i, reply_data in enumerate(replies_data):
            reply_data["post_id"] = post_data["post_id"]
            reply_data["reply_id"] = f"reply_{i}"
            reply_data["created_at"] = datetime(2024, 1, 1, 0, i)  # 递增时间
            store.create_reply(reply_data)
        
        # 获取回复并验证顺序
        fetched_replies = store.get_post_replies(post_data["post_id"])
        
        for i in range(len(fetched_replies) - 1):
            assert fetched_replies[i]["created_at"] <= fetched_replies[i + 1]["created_at"]


class TestSearchResultRelevance:
    """
    Property 4: Search Result Relevance
    
    *For any* search query, all returned posts SHALL contain the search keyword
    in either title or content, and when filtered by forum_id, all results SHALL belong to that forum.
    
    **Validates: Requirements 4.1, 4.2, 4.3**
    """
    
    @given(
        forum_strategy(),
        st.lists(post_strategy(), min_size=1, max_size=5),
        st.text(min_size=1, max_size=20).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_search_results_contain_keyword(self, forum_data, posts_data, keyword):
        """
        Feature: openboard-forum, Property 4: Search Result Relevance
        搜索结果必须包含关键词
        """
        store = MockForumStore()
        
        # 创建并激活论坛
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], True)
        
        # 创建帖子
        for i, post_data in enumerate(posts_data):
            post_data["forum_id"] = forum_data["forum_id"]
            post_data["post_id"] = f"post_{i}"
            store.create_post(post_data)
        
        # 搜索
        results = store.search_posts(keyword)
        
        # 验证所有结果都包含关键词
        for result in results:
            keyword_lower = keyword.lower()
            assert (
                keyword_lower in result["title"].lower() or
                keyword_lower in result["content"].lower()
            ), f"Result does not contain keyword: {keyword}"
    
    @given(
        st.lists(forum_strategy(), min_size=2, max_size=3),
        st.text(min_size=1, max_size=10).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_search_filter_by_forum(self, forums_data, keyword):
        """
        Feature: openboard-forum, Property 4: Search Result Relevance
        按论坛筛选时，结果只包含该论坛的帖子
        """
        store = MockForumStore()
        
        # 创建多个论坛
        for i, forum_data in enumerate(forums_data):
            forum_data["forum_id"] = f"forum_{i}"
            store.create_forum(forum_data)
            store.approve_forum(forum_data["forum_id"], True)
            
            # 每个论坛创建一个包含关键词的帖子
            post_data = {
                "post_id": f"post_{i}",
                "forum_id": forum_data["forum_id"],
                "title": f"Title with {keyword}",
                "content": "Some content",
                "author_id": "user1",
                "reply_count": 0,
                "is_deleted": False,
                "created_at": datetime.now(),
            }
            store.create_post(post_data)
        
        # 按第一个论坛筛选搜索
        target_forum_id = "forum_0"
        results = store.search_posts(keyword, forum_id=target_forum_id)
        
        # 验证所有结果都属于目标论坛
        for result in results:
            assert result["forum_id"] == target_forum_id


class TestUserBanUnbanCycle:
    """
    Property 6: User Ban/Unban Cycle
    
    *For any* user banned by a teacher, the user's posting attempts SHALL fail with an error.
    After unbanning, the user SHALL be able to post again.
    
    **Validates: Requirements 6.1, 6.2, 6.3**
    """
    
    @given(forum_strategy(), post_strategy(), user_id_strategy)
    @settings(max_examples=100)
    def test_banned_user_cannot_post(self, forum_data, post_data, user_id):
        """
        Feature: openboard-forum, Property 6: User Ban/Unban Cycle
        被封禁的用户无法发帖
        """
        store = MockForumStore()
        
        # 创建并激活论坛
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], True)
        
        # 封禁用户
        store.ban_user(user_id)
        
        # 尝试发帖
        post_data["forum_id"] = forum_data["forum_id"]
        post_data["author_id"] = user_id
        
        with pytest.raises(ValueError, match="banned"):
            store.create_post(post_data)
    
    @given(forum_strategy(), post_strategy(), user_id_strategy)
    @settings(max_examples=100)
    def test_unbanned_user_can_post(self, forum_data, post_data, user_id):
        """
        Feature: openboard-forum, Property 6: User Ban/Unban Cycle
        解封后用户可以发帖
        """
        store = MockForumStore()
        
        # 创建并激活论坛
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], True)
        
        # 封禁然后解封用户
        store.ban_user(user_id)
        store.unban_user(user_id)
        
        # 发帖应该成功
        post_data["forum_id"] = forum_data["forum_id"]
        post_data["author_id"] = user_id
        
        result = store.create_post(post_data)
        assert result["author_id"] == user_id
    
    @given(forum_strategy(), post_strategy(), reply_strategy(), user_id_strategy)
    @settings(max_examples=100)
    def test_banned_user_cannot_reply(self, forum_data, post_data, reply_data, user_id):
        """
        Feature: openboard-forum, Property 6: User Ban/Unban Cycle
        被封禁的用户无法回复
        """
        store = MockForumStore()
        
        # 创建并激活论坛
        store.create_forum(forum_data)
        store.approve_forum(forum_data["forum_id"], True)
        
        # 创建帖子（用其他用户）
        post_data["forum_id"] = forum_data["forum_id"]
        post_data["author_id"] = "other_user"
        store.create_post(post_data)
        
        # 封禁用户
        store.ban_user(user_id)
        
        # 尝试回复
        reply_data["post_id"] = post_data["post_id"]
        reply_data["author_id"] = user_id
        
        with pytest.raises(ValueError, match="banned"):
            store.create_reply(reply_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
