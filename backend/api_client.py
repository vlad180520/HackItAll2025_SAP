"""API client for external evaluation platform."""

import logging
import time
import requests
from typing import Dict, List, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when API returns validation error (HTTP 400)."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}


class ExternalAPIClient:
    """HTTP client for external evaluation platform."""
    
    def __init__(self, base_url: str, api_key_header: str = "API-KEY", timeout: int = 30):
        """
        Initialize API client.
        
        Args:
            base_url: Base URL of the evaluation platform
            api_key_header: Header name for API key
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.api_key_header = api_key_header
        self.timeout = timeout
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        api_key: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        session_id: Optional[str] = None,
        return_text: bool = False,
    ) -> Dict:
        """
        Make HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            api_key: API key for authentication
            json_data: JSON payload for POST requests
            params: Query parameters
            session_id: Optional session ID for SESSION-ID header
            return_text: If True, return text response instead of JSON
            
        Returns:
            Parsed JSON response or text if return_text=True
            
        Raises:
            ValidationError: For HTTP 400 responses
            requests.RequestException: For other HTTP errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = {self.api_key_header: api_key}
        if session_id:
            headers["SESSION-ID"] = session_id
        
        try:
            if method.upper() == "POST":
                response = self.session.post(
                    url, json=json_data, headers=headers, params=params, timeout=self.timeout
                )
            else:
                response = self.session.get(
                    url, headers=headers, params=params, timeout=self.timeout
                )
            
            # Handle validation errors
            if response.status_code == 400:
                error_details = response.json() if response.content else {}
                error_msg = error_details.get("detail", error_details.get("message", "Validation error"))
                raise ValidationError(error_msg, error_details)
            
            # Raise for other HTTP errors
            response.raise_for_status()
            
            # Return text or JSON
            if return_text:
                return response.text.strip()
            return response.json() if response.content else {}
            
        except requests.Timeout:
            logger.error(f"Request timeout for {endpoint}")
            raise
        except requests.RequestException as e:
            logger.error(f"Request error for {endpoint}: {e}")
            raise
    
    def start_session(self, api_key: str) -> str:
        """
        Start a new session with the evaluation platform.
        
        Args:
            api_key: API key for authentication
            
        Returns:
            Session ID as string
        """
        logger.info("Starting session with evaluation platform")
        session_id = self._make_request("POST", "/api/v1/session/start", api_key, return_text=True)
        logger.info(f"Session started: {session_id}")
        return session_id
    
    def play_round(
        self,
        api_key: str,
        session_id: str,
        day: int,
        hour: int,
        flight_loads: List[Dict],
        kit_purchasing_orders: Dict[str, int],
    ) -> Dict:
        """
        Play a round of the simulation.
        
        Args:
            api_key: API key for authentication
            session_id: Current session ID
            day: Current day
            hour: Current hour
            flight_loads: List of flight load decisions (FlightLoadDto format)
            kit_purchasing_orders: Purchase orders as PerClassAmount dict
            
        Returns:
            HourResponseDto including penalties, flight updates, etc.
        """
        # Convert flight loads to API format
        flight_loads_api = []
        for load in flight_loads:
            # Convert kits_per_class from uppercase to camelCase
            kits = load.get("kits_per_class", {})
            loaded_kits = {
                "first": kits.get("FIRST", 0),
                "business": kits.get("BUSINESS", 0),
                "premiumEconomy": kits.get("PREMIUM_ECONOMY", 0),
                "economy": kits.get("ECONOMY", 0),
            }
            flight_loads_api.append({
                "flightId": load.get("flight_id"),
                "loadedKits": loaded_kits,
            })
        
        # Convert purchases to PerClassAmount format
        purchasing_orders = {
            "first": kit_purchasing_orders.get("FIRST", 0),
            "business": kit_purchasing_orders.get("BUSINESS", 0),
            "premiumEconomy": kit_purchasing_orders.get("PREMIUM_ECONOMY", 0),
            "economy": kit_purchasing_orders.get("ECONOMY", 0),
        }
        
        payload = {
            "day": day,
            "hour": hour,
            "flightLoads": flight_loads_api,
            "kitPurchasingOrders": purchasing_orders,
        }
        
        logger.debug(f"Playing round {day}:{hour} with {len(flight_loads_api)} loads")
        response = self._make_request(
            "POST", 
            "/api/v1/play/round", 
            api_key, 
            json_data=payload,
            session_id=session_id
        )
        
        # Log penalties if present
        penalties = response.get("penalties", [])
        if penalties:
            logger.warning(f"Received {len(penalties)} penalties in round {day}:{hour}")
        
        return response
    
    def stop_session(self, api_key: str, session_id: str) -> Dict:
        """
        Stop the current session.
        
        Args:
            api_key: API key for authentication
            session_id: Current session ID
            
        Returns:
            HourResponseDto with final session report
        """
        logger.info(f"Stopping session {session_id}")
        response = self._make_request("POST", "/api/v1/session/end", api_key, session_id=session_id)
        return response

