import asyncio
import pytz

from datetime import datetime
from tortoise import Model, fields


class Accounts(Model):
    email = fields.CharField(max_length=255, unique=True)
    email_password = fields.CharField(max_length=255, null=True)

    user_id = fields.CharField(max_length=255, null=True)
    referral_code = fields.CharField(max_length=255, null=True)

    session_token = fields.CharField(max_length=2048, null=True)
    privy_auth_token = fields.CharField(max_length=2048, null=True)
    extension_token = fields.CharField(max_length=2048, null=True)
    refresh_token = fields.CharField(max_length=1024, null=True)

    active_account_proxy = fields.CharField(max_length=255, null=True)
    sleep_until = fields.DatetimeField(null=True)

    class Meta:
        table = "dawn_accounts"

    # ===== Basic getters =====

    @classmethod
    async def get_account(cls, email: str):
        return await cls.get_or_none(email=email)

    @classmethod
    async def get_accounts(cls):
        return await cls.all()

    @classmethod
    async def get_accounts_stats(cls, emails: list[str] | None = None) -> tuple[int, int]:
        query = cls.all()
        if emails:
            query = query.filter(email__in=emails)

        accounts = await query
        now = datetime.now(pytz.UTC)

        accounts_with_expired_sleep = len([
            a for a in accounts
            if (a.sleep_until is None) or (a.sleep_until <= now)
        ])

        accounts_waiting_sleep = len([
            a for a in accounts
            if a.sleep_until and a.sleep_until > now
        ])

        return accounts_with_expired_sleep, accounts_waiting_sleep

    # ===== Proxy helpers =====

    async def update_account_proxy(self, proxy: str | None):
        self.active_account_proxy = proxy
        await self.save(update_fields=["active_account_proxy"])

    @classmethod
    async def get_account_proxy(cls, email: str) -> str:
        account = await cls.get_account(email=email)
        return account.active_account_proxy if account and account.active_account_proxy else ""

    # ===== Create / update =====

    @classmethod
    async def create_or_update_account(
        cls,
        email: str,
        email_password: str | None = None,
        user_id: str | None = None,
        referral_code: str | None = None,
        session_token: str | None = None,
        privy_auth_token: str | None = None,
        extension_token: str | None = None,
        refresh_token: str | None = None,
        proxy: str | None = None,
    ) -> "Accounts":
        account = await cls.get_account(email=email)

        if account is None:
            account = await cls.create(
                email=email,
                email_password=email_password,
                user_id=user_id,
                referral_code=referral_code,
                session_token=session_token,
                privy_auth_token=privy_auth_token,
                extension_token=extension_token,
                refresh_token=refresh_token,
                active_account_proxy=proxy,
            )
            return account

        # update existing
        update_fields: list[str] = []

        if email_password is not None:
            account.email_password = email_password
            update_fields.append("email_password")
        if user_id is not None:
            account.user_id = user_id
            update_fields.append("user_id")
        if referral_code is not None:
            account.referral_code = referral_code
            update_fields.append("referral_code")
        if session_token is not None:
            account.session_token = session_token
            update_fields.append("session_token")
        if privy_auth_token is not None:
            account.privy_auth_token = privy_auth_token
            update_fields.append("privy_auth_token")
        if extension_token is not None:
            account.extension_token = extension_token
            update_fields.append("extension_token")
        if refresh_token is not None:
            account.refresh_token = refresh_token
            update_fields.append("refresh_token")
        if proxy is not None:
            account.active_account_proxy = proxy
            update_fields.append("active_account_proxy")

        if update_fields:
            await account.save(update_fields=update_fields)

        return account

    async def update_account(
        self,
        email_password: str | None = None,
        user_id: str | None = None,
        referral_code: str | None = None,
        session_token: str | None = None,
        privy_auth_token: str | None = None,
        extension_token: str | None = None,
        refresh_token: str | None = None,
        proxy: str | None = None,
    ) -> "Accounts":
        update_fields: list[str] = []

        if email_password is not None:
            self.email_password = email_password
            update_fields.append("email_password")
        if user_id is not None:
            self.user_id = user_id
            update_fields.append("user_id")
        if referral_code is not None:
            self.referral_code = referral_code
            update_fields.append("referral_code")
        if session_token is not None:
            self.session_token = session_token
            update_fields.append("session_token")
        if privy_auth_token is not None:
            self.privy_auth_token = privy_auth_token
            update_fields.append("privy_auth_token")
        if extension_token is not None:
            self.extension_token = extension_token
            update_fields.append("extension_token")
        if refresh_token is not None:
            self.refresh_token = refresh_token
            update_fields.append("refresh_token")
        if proxy is not None:
            self.active_account_proxy = proxy
            update_fields.append("active_account_proxy")

        if update_fields:
            await self.save(update_fields=update_fields)

        return self

    # ===== Token & meta getters =====

    @classmethod
    async def get_user_id(cls, email: str) -> str | None:
        acc = await cls.get_account(email=email)
        return acc.user_id if acc else None

    @classmethod
    async def get_referral_code(cls, email: str) -> str | None:
        acc = await cls.get_account(email=email)
        return acc.referral_code if acc else None

    @classmethod
    async def get_session_token(cls, email: str) -> str | None:
        acc = await cls.get_account(email=email)
        return acc.session_token if acc else None

    @classmethod
    async def get_privy_auth_token(cls, email: str) -> str | None:
        acc = await cls.get_account(email=email)
        return acc.privy_auth_token if acc else None

    @classmethod
    async def get_extension_token(cls, email: str) -> str | None:
        acc = await cls.get_account(email=email)
        return acc.extension_token if acc else None

    @classmethod
    async def get_refresh_token(cls, email: str) -> str | None:
        acc = await cls.get_account(email=email)
        return acc.refresh_token if acc else None

    # ===== Delete =====

    @classmethod
    async def delete_account(cls, email: str) -> bool:
        account = await cls.get_account(email=email)
        if account is None:
            return False
        await account.delete()
        return True

    # ===== Sleep helpers =====

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

    # ===== Bulk ops =====

    @classmethod
    async def clear_all_accounts_proxies(cls, concurrency: int = 200) -> int:
        accounts = await cls.all()
        sem = asyncio.Semaphore(concurrency)

        async def clear_proxy(acc: "Accounts"):
            async with sem:
                if acc.active_account_proxy:
                    acc.active_account_proxy = None
                    await acc.save(update_fields=["active_account_proxy"])

        await asyncio.gather(*(clear_proxy(a) for a in accounts))
        return len(accounts)
