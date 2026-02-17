import asyncio
from sqlalchemy import text
from app.core.database import async_engine


async def main():
    async with async_engine.begin() as conn:
        # Find the config definition id first
        result = await conn.execute(
            text("SELECT id, key FROM system_configs WHERE key = 'login_captcha_enabled'")
        )
        config_row = result.first()
        if not config_row:
            print("No login_captcha_enabled config definition found")
            return

        config_id = config_row[0]
        print(f"Config definition: id={config_id}, key={config_row[1]}")

        # Check if there's a value override
        result = await conn.execute(
            text("SELECT id, config_id, value, tenant_id FROM system_config_values WHERE config_id = :cid"),
            {"cid": config_id},
        )
        val_row = result.first()
        if val_row:
            print(f"Current value: id={val_row[0]}, value={val_row[2]}, tenant_id={val_row[3]}")
            await conn.execute(
                text("UPDATE system_config_values SET value = 'false' WHERE config_id = :cid AND tenant_id IS NULL"),
                {"cid": config_id},
            )
            print("Captcha disabled (updated)")
        else:
            # Insert a platform-level override
            await conn.execute(
                text("INSERT INTO system_config_values (config_id, value, created_at, updated_at) VALUES (:cid, 'false', NOW(), NOW())"),
                {"cid": config_id},
            )
            print("Captcha disabled (inserted)")


asyncio.run(main())
