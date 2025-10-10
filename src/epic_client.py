"""Epic FHIR API client with OAuth2 authentication."""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
import jwt

logger = logging.getLogger(__name__)


@dataclass
class TokenCache:
    """Cache for OAuth2 access token."""

    token: str
    expiry: datetime


class EpicFHIRClient:
    """Epic FHIR API client with OAuth2 backend systems authentication."""

    def __init__(
        self,
        client_id: str,
        private_key_path: str,
        token_url: str,
        fhir_base_url: str,
    ):
        """Initialize Epic FHIR client.

        Args:
            client_id: Epic client ID (from developer portal)
            private_key_path: Path to RSA private key file
            token_url: Epic OAuth2 token endpoint
            fhir_base_url: Epic FHIR API base URL
        """
        self.client_id = client_id
        self.private_key_path = private_key_path
        self.token_url = token_url
        self.fhir_base_url = fhir_base_url
        self._token_cache: TokenCache | None = None
        self._http_client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close HTTP client connection."""
        await self._http_client.aclose()

    def _generate_jwt(self) -> str:
        """Generate JWT for client authentication.

        Returns:
            Signed JWT assertion
        """
        # Load private key
        with open(self.private_key_path, "r") as key_file:
            private_key = key_file.read()
        
        now = int(time.time())

        headers = {
            "alg": "RS384",
            "typ": "JWT",
            "kid": "epic-fhir-key-1",  # Must match JWKS
        }

        payload = {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_url,
            "jti": str(uuid.uuid4()),
            "iat": now,
            "nbf": now,  # Not before - REQUIRED by Epic
            "exp": now + 300,  # 5 minute expiration
        }

        return jwt.encode(payload, private_key, algorithm="RS384", headers=headers)

    async def _request_token(self, scopes: list[str]) -> dict[str, Any]:
        """Request access token from Epic OAuth2 endpoint.

        Args:
            scopes: List of FHIR scopes in SMART v2 format (e.g., ['system/Patient.rs'])

        Returns:
            Token response with access_token and expires_in
        """
        assertion = self._generate_jwt()

        data = {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": assertion,
            "scope": " ".join(scopes),
        }

        logger.debug(f"Requesting token with scopes: {scopes}")
        logger.debug(f"Token endpoint: {self.token_url}")
        logger.debug(f"Client ID: {self.client_id}")
        
        response = await self._http_client.post(self.token_url, data=data)
        
        # Log error details for debugging
        if response.status_code != 200:
            logger.error(f"Token request failed with status {response.status_code}")
            logger.error(f"Response: {response.text}")
            try:
                error_detail = response.json()
                logger.error(f"Error detail: {error_detail}")
            except Exception:
                pass
        
        response.raise_for_status()

        token_data = response.json()
        logger.info("Successfully obtained access token")
        return token_data

    async def get_token(self, scopes: list[str]) -> str:
        """Get cached or fresh access token.

        Args:
            scopes: Required FHIR scopes

        Returns:
            Valid access token
        """
        now = datetime.now()

        # Return cached token if still valid (with 5-min buffer)
        if self._token_cache and now < (self._token_cache.expiry - timedelta(minutes=5)):
            logger.debug("Using cached access token")
            return self._token_cache.token

        # Get new token
        logger.debug("Requesting new access token")
        token_data = await self._request_token(scopes)
        self._token_cache = TokenCache(
            token=token_data["access_token"],
            expiry=now + timedelta(seconds=token_data["expires_in"]),
        )

        return self._token_cache.token

    def _determine_scopes(self, path: str) -> list[str]:
        """Determine required FHIR scopes from API path.

        Args:
            path: FHIR API path (e.g., 'Patient/123' or 'Observation')

        Returns:
            List of required scopes in SMART v2 format (.rs for read+search)
        """
        # Extract resource type from path
        resource_type = path.split("/")[0].split("?")[0]
        # SMART v2 format: .rs for read+search (replaces v1 .read)
        return [f"system/{resource_type}.rs"]

    async def fhir_request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated FHIR API request.

        Args:
            path: FHIR resource path (e.g., 'Patient/123')
            params: Query parameters

        Returns:
            FHIR resource or bundle
        """
        scopes = self._determine_scopes(path)
        token = await self.get_token(scopes)

        url = f"{self.fhir_base_url}/{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/fhir+json",
        }

        logger.debug(f"FHIR request: GET {url}")
        response = await self._http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        return response.json()

    # Convenience methods for common FHIR queries

    async def get_patient(self, patient_id: str) -> dict[str, Any]:
        """Get patient by FHIR ID."""
        return await self.fhir_request(f"Patient/{patient_id}")

    async def search_patients(self, **params) -> dict[str, Any]:
        """Search for patients."""
        return await self.fhir_request("Patient", params=params)

    async def get_observations(
        self,
        patient_id: str,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Get patient observations (labs, vitals, etc.)."""
        params = {"patient": patient_id}
        if category:
            params["category"] = category
        return await self.fhir_request("Observation", params=params)

    async def get_conditions(self, patient_id: str) -> dict[str, Any]:
        """Get patient conditions/diagnoses."""
        return await self.fhir_request("Condition", params={"patient": patient_id})

    async def get_medications(self, patient_id: str) -> dict[str, Any]:
        """Get patient medications."""
        return await self.fhir_request("MedicationRequest", params={"patient": patient_id})

    async def get_allergies(self, patient_id: str) -> dict[str, Any]:
        """Get patient allergies and intolerances."""
        return await self.fhir_request("AllergyIntolerance", params={"patient": patient_id})

    async def get_immunizations(self, patient_id: str) -> dict[str, Any]:
        """Get patient immunization history."""
        return await self.fhir_request("Immunization", params={"patient": patient_id})

    async def get_procedures(self, patient_id: str) -> dict[str, Any]:
        """Get patient procedures."""
        return await self.fhir_request("Procedure", params={"patient": patient_id})
