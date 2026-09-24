FROM pgvector/pgvector:pg16

# Defaults match .env. Runtime env (docker compose / --env-file) overrides them.
ENV DB_USER=postgres \
    DB_PASSWORD=postgres \
    DB_NAME=build_phase_p029 \
    DB_PORT=5432

COPY entrypoint.sh /usr/local/bin/map-db-env.sh
COPY init/01-pgvector.sql /docker-entrypoint-initdb.d/01-pgvector.sql
RUN chmod +x /usr/local/bin/map-db-env.sh

EXPOSE 5432

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD pg_isready -U "$DB_USER" -d "$DB_NAME" -p "$DB_PORT"

ENTRYPOINT ["map-db-env.sh"]
CMD ["postgres"]
