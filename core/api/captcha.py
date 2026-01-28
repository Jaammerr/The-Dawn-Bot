"""
CapSolver integration for solving Cloudflare Turnstile captcha.
"""
import asyncio
from typing import Optional
import httpx
from loguru import logger


class CaptchaSolver:
    """Solver for Cloudflare Turnstile captcha using CapSolver API."""
    
    CAPSOLVER_API_URL = "https://api.capsolver.com"
    TURNSTILE_SITEKEY = "0x4AAAAAAAM8ceq5KhP1uJBt"
    TURNSTILE_URL = "https://auth.privy.io"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def solve_turnstile(self, proxy: str = None) -> Optional[str]:
        """
        Solve Cloudflare Turnstile captcha.
        
        Args:
            proxy: Optional proxy string in format user:pass@host:port
            
        Returns:
            Captcha token string or None if failed
        """
        try:
            logger.info("Solving Turnstile captcha via CapSolver...")
            
            # Create task - always use ProxyLess for simplicity
            task_data = {
                "clientKey": self.api_key,
                "task": {
                    "type": "AntiTurnstileTaskProxyLess",
                    "websiteURL": self.TURNSTILE_URL,
                    "websiteKey": self.TURNSTILE_SITEKEY,
                }
            }
            
            async with httpx.AsyncClient(timeout=120) as client:
                # Create task
                response = await client.post(
                    f"{self.CAPSOLVER_API_URL}/createTask",
                    json=task_data
                )
                result = response.json()
                
                if result.get("errorId") != 0:
                    logger.error(f"CapSolver create task error: {result.get('errorDescription')}")
                    return None
                    
                task_id = result.get("taskId")
                logger.debug(f"CapSolver task created: {task_id}")
                
                # Poll for result
                for attempt in range(60):  # Max 60 attempts, 2 seconds each = 2 minutes
                    await asyncio.sleep(2)
                    
                    response = await client.post(
                        f"{self.CAPSOLVER_API_URL}/getTaskResult",
                        json={
                            "clientKey": self.api_key,
                            "taskId": task_id
                        }
                    )
                    result = response.json()
                    
                    if result.get("errorId") != 0:
                        logger.error(f"CapSolver get result error: {result.get('errorDescription')}")
                        return None
                        
                    status = result.get("status")
                    
                    if status == "ready":
                        token = result.get("solution", {}).get("token")
                        logger.success("Turnstile captcha solved successfully!")
                        return token
                    elif status == "failed":
                        logger.error("CapSolver task failed")
                        return None
                        
                logger.error("CapSolver timeout - no result after 2 minutes")
                return None
                
        except Exception as e:
            logger.error(f"CapSolver error: {e}")
            return None
