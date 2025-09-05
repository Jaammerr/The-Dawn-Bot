import asyncio
import pytz

from datetime import datetime
from tortoise import Model, fields


class Accounts(Model):
    email = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255, null=True)
    app_id = fields.CharField(max_length=50, null=True)
    auth_token = fields.CharField(max_length=1024, null=True)

    active_account_proxy = fields.CharField(max_length=255, null=True)
    sleep_until = fields.DatetimeField(null=True)

    class Meta:
        table = "dawn_accounts_v1.9"

    @classmethod
    async def get_account(cls, email: str):
        return await cls.get_or_none(email=email)

    @classmethod
    async def get_accounts(cls):
        return await cls.all()

    @classmethod
    async def get_accounts_stats(cls, emails: list[str] = None) -> tuple[int, int]:
        query = cls.all()
        if emails:
            query = query.filter(email__in=emails)

        accounts = await query
        now = datetime.now(pytz.UTC)

        accounts_with_expired_sleep = len([
            account for account in accounts
            if (account.sleep_until is None) or (account.sleep_until <= now)
        ])

        accounts_waiting_sleep = len([
            account for account in accounts
            if account.sleep_until and account.sleep_until > now
        ])

        return accounts_with_expired_sleep, accounts_waiting_sleep

    async def update_account_proxy(self, proxy: str):
        self.active_account_proxy = proxy
        await self.save(update_fields=["active_account_proxy"])

    @classmethod
    async def get_account_proxy(cls, email: str) -> str:
        account = await cls.get_account(email=email)
        if account:
            return account.active_account_proxy

        return ""

    @classmethod
    async def create_or_update_account(
            cls,
            email: str,
            password: str | None = None,
            app_id: str | None = None,
            auth_token: str | None = None,
            proxy: str | None = None,
    ) -> "Accounts":
        account = await cls.get_account(email=email)
        if account is None:
            account = await cls.create(
                email=email,
                password=password,
                auth_token=auth_token,
                app_id=app_id,
                active_account_proxy=proxy,
            )
            return account

        update_fields: list[str] = []

        if password is not None:
            account.password = password
            update_fields.append("password")
        if app_id is not None:
            account.app_id = app_id
            update_fields.append("app_id")
        if auth_token is not None:
            account.auth_token = auth_token
            update_fields.append("auth_token")
        if proxy is not None:
            account.active_account_proxy = proxy
            update_fields.append("active_account_proxy")

        if update_fields:
            await account.save(update_fields=update_fields)

        return account

    async def update_account(
            self,
            password: str | None = None,
            app_id: str | None = None,
            auth_token: str | None = None,
            proxy: str | None = None,
    ) -> "Accounts":
        update_fields: list[str] = []

        if password is not None:
            self.password = password
            update_fields.append("password")
        if app_id is not None:
            self.app_id = app_id
            update_fields.append("app_id")
        if auth_token is not None:
            print(f"Updating auth_token for {self.email} | {auth_token}")
            self.auth_token = auth_token
            update_fields.append("auth_token")
        if proxy is not None:
            self.active_account_proxy = proxy
            update_fields.append("active_account_proxy")

        if update_fields:
            await self.save(update_fields=update_fields)

        return self

    @classmethod
    async def get_app_id(cls, email: str) -> str | None:
        account = await cls.get_account(email=email)
        if account is None:
            return None

        return account.app_id

    @classmethod
    async def get_auth_token(cls, email: str) -> str | None:
        account = await cls.get_account(email=email)
        if account is None:
            return None

        return account.auth_token

    @classmethod
    async def delete_account(cls, email: str) -> bool:
        account = await cls.get_account(email=email)
        if account is None:
            return False

        await account.delete()
        return True

    async def set_sleep_until(self, sleep_until: datetime) -> "Accounts":
        if not isinstance(sleep_until, datetime):
            raise ValueError("sleep_until must be a datetime object")

        if sleep_until.tzinfo is None:
            sleep_until = pytz.UTC.localize(sleep_until)
        else:
            sleep_until = sleep_until.astimezone(pytz.UTC)

        self.sleep_until = sleep_until
        await self.save(update_fields=["sleep_until"])
        return self

    async def clear_all_accounts_proxies(self) -> int:
        async def clear_proxy(account: Accounts):
            async with asyncio.Semaphore(500):
                if account.active_account_proxy:
                    account.active_account_proxy = None
                    await account.save(update_fields=["active_account_proxy"])

        accounts = await self.all()
        tasks = [asyncio.create_task(clear_proxy(account)) for account in accounts]
        await asyncio.gather(*tasks)

        return len(accounts)
