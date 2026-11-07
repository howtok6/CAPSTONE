"""Compatibilidad con el comando original del piloto de Las Condes."""

from app.capture_study import capture as capture
from app.capture_study import main

if __name__ == "__main__":
    raise SystemExit(main())
