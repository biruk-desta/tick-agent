FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KANYARAASI_RECOVERY_MODE=aggressive \
    KANYARAASI_MATCH_POLICY=adaptive \
    KANYARAASI_NAV_CACHE=on
WORKDIR /bot
COPY bot.py mechfight.py arena_model.py body_stats.py navigation.py navigation_cache.py combat.py match_policy.py firstparty_movement.py ./
USER 65534:65534
ENTRYPOINT ["python3", "-u", "/bot/bot.py"]
