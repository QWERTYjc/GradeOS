"""检查和清理 Redis 中的批改任务 slot"""
import asyncio
import redis.asyncio as redis


async def check_and_clear_slots():
    """检查并清理 Redis 中的批改任务 slot"""
    r = await redis.from_url("redis://localhost:6379", decode_responses=True)
    
    try:
        # 查找所有批改相关的 key
        print("=== 查找所有批改相关的 Redis keys ===")
        keys = await r.keys("grading_run:*")
        print(f"找到 {len(keys)} 个 keys:")
        for key in keys:
            print(f"  - {key}")
        
        # 检查 active slots
        print("\n=== 检查 active slots ===")
        active_keys = [k for k in keys if ":active:" in k]
        for key in active_keys:
            members = await r.zrange(key, 0, -1, withscores=True)
            print(f"\n{key}:")
            if members:
                for member, score in members:
                    print(f"  - {member}: score={score}")
            else:
                print("  (空)")
        
        # 检查 queue
        print("\n=== 检查 queue ===")
        queue_keys = [k for k in keys if ":queue:" in k]
        for key in queue_keys:
            members = await r.zrange(key, 0, -1, withscores=True)
            print(f"\n{key}:")
            if members:
                for member, score in members:
                    print(f"  - {member}: score={score}")
            else:
                print("  (空)")
        
        # 询问是否清理
        print("\n=== 清理选项 ===")
        print("是否要清理所有 active slots 和 queue? (y/n)")
        # 自动清理
        print("自动清理所有 slots...")
        
        # 清理 active slots
        for key in active_keys:
            deleted = await r.delete(key)
            print(f"删除 {key}: {deleted}")
        
        # 清理 queue
        for key in queue_keys:
            deleted = await r.delete(key)
            print(f"删除 {key}: {deleted}")
        
        print("\n清理完成！")
        
    finally:
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(check_and_clear_slots())
