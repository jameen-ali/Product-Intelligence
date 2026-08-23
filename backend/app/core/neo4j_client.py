import logging
import time
from typing import Dict, Any, List, Optional

try:
    from neo4j import GraphDatabase, Driver
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    Driver = None
    NEO4J_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)

class Neo4jClient:
    def __init__(self):
        self._driver: Optional[Driver] = None
        self._last_error: Optional[str] = None

    def _get_session_kwargs(self) -> Dict[str, Any]:
        """Returns session kwargs. Omits database if set to 'neo4j' default for AuraDB compatibility."""
        if settings.NEO4J_DATABASE and settings.NEO4J_DATABASE != "neo4j":
            return {"database": settings.NEO4J_DATABASE}
        return {}

    def connect(self):
        if not NEO4J_AVAILABLE:
            self._last_error = "neo4j package not installed"
            return
        if not self._driver:
            uri = settings.NEO4J_URI
            username = settings.NEO4J_USERNAME
            password = settings.NEO4J_PASSWORD

            potential_users = []
            if "." in uri and "databases.neo4j.io" in uri:
                subdomain = uri.split("://")[-1].split(".")[0]
                if subdomain:
                    potential_users.append(subdomain)
            if username and username not in potential_users:
                potential_users.append(username)
            if "neo4j" not in potential_users:
                potential_users.append("neo4j")

            connected = False
            last_exc = None
            sess_kwargs = self._get_session_kwargs()

            for user_candidate in potential_users:
                schemes = [uri]
                if uri.startswith("neo4j+s://"):
                    schemes.append(uri.replace("neo4j+s://", "neo4j+ssc://"))
                    schemes.append(uri.replace("neo4j+s://", "bolt+s://"))
                    schemes.append(uri.replace("neo4j+s://", "bolt+ssc://"))

                for scheme in schemes:
                    driver = None
                    try:
                        driver = GraphDatabase.driver(
                            scheme,
                            auth=(user_candidate, password)
                        )
                        driver.verify_connectivity()
                        with driver.session(**sess_kwargs) as s:
                            s.run("RETURN 1 AS health")
                        self._driver = driver
                        connected = True
                        self._last_error = None
                        logger.info(f"Successfully connected to Neo4j at {scheme} with user '{user_candidate}'")
                        break
                    except Exception as err:
                        last_exc = err
                        if driver:
                            try:
                                driver.close()
                            except Exception:
                                pass
                if connected:
                    break

            if not connected:
                self._last_error = str(last_exc)
                logger.warning(f"Neo4j connection failed at {uri}: {last_exc}")
                self._driver = None

    def close(self):
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None

    def check_health(self) -> Dict[str, Any]:
        uri = settings.NEO4J_URI
        if not NEO4J_AVAILABLE:
            return {"status": "unhealthy", "uri": uri, "error": "neo4j package not installed"}
        try:
            if not self._driver:
                self.connect()
            if not self._driver:
                return {"status": "unhealthy", "uri": uri, "error": self._last_error or "Neo4j driver connection is unavailable"}
            
            self._driver.verify_connectivity()

            sess_kwargs = self._get_session_kwargs()
            with self._driver.session(**sess_kwargs) as session:
                result = session.run("RETURN 1 AS health")
                record = result.single()
                if record and record["health"] == 1:
                    return {"status": "healthy", "uri": uri}
                return {"status": "unhealthy", "uri": uri, "error": "Unexpected health check response"}
        except Exception as e:
            self._driver = None
            self._last_error = str(e)
            return {"status": "unhealthy", "uri": uri, "error": str(e)}

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self._driver:
            self.connect()
        if not self._driver:
            raise RuntimeError(f"Neo4j driver connection is unavailable: {self._last_error}")
        
        try:
            sess_kwargs = self._get_session_kwargs()
            with self._driver.session(**sess_kwargs) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            self._driver = None
            self._last_error = str(e)
            raise e

neo4j_client = Neo4jClient()
