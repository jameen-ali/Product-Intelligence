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
        self._last_attempt: float = 0

    def connect(self):
        if not NEO4J_AVAILABLE:
            return
        if not self._driver:
            now = time.time()
            # Throttle connection retries to once every 2 seconds
            if now - self._last_attempt < 2.0:
                return
            self._last_attempt = now
            uri = settings.NEO4J_URI
            username = settings.NEO4J_USERNAME
            password = settings.NEO4J_PASSWORD

            try:
                try:
                    self._driver = GraphDatabase.driver(
                        uri,
                        auth=(username, password)
                    )
                    with self._driver.session(database=settings.NEO4J_DATABASE) as s:
                        s.run("RETURN 1")
                except Exception as first_err:
                    if uri.startswith("neo4j+s://"):
                        fallback_uri = uri.replace("neo4j+s://", "neo4j+ssc://")
                        self._driver = GraphDatabase.driver(
                            fallback_uri,
                            auth=(username, password)
                        )
                        with self._driver.session(database=settings.NEO4J_DATABASE) as s:
                            s.run("RETURN 1")
                    else:
                        raise first_err
                logger.info(f"Connected to Neo4j at {uri} (user={username})")
            except Exception as e:
                logger.warning(f"Neo4j offline at {uri} (user={username}): {e}")
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
                return {"status": "unhealthy", "uri": uri, "error": "Neo4j database offline or unreachable"}
            
            with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run("RETURN 1 AS num")
                record = result.single()
                if record and record["num"] == 1:
                    return {"status": "healthy", "uri": uri}
                return {"status": "unhealthy", "uri": uri, "error": "Unexpected ping response"}
        except Exception as e:
            self._driver = None
            return {"status": "unhealthy", "uri": uri, "error": str(e)}

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self._driver:
            self.connect()
        if not self._driver:
            raise RuntimeError("Neo4j driver connection is unavailable")
        
        try:
            with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            self._driver = None
            raise e

neo4j_client = Neo4jClient()
