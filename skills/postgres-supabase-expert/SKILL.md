---
name: "postgres-supabase-expert"
description: "Advanced guide for PostgreSQL and Supabase. Covers schema design, RLS, query optimization, migrations, Edge Functions, and database security."
---

# Postgres & Supabase Expert Guide

This skill provides comprehensive rules for designing, optimizing, and securing databases on PostgreSQL and the Supabase platform.

## 🏗 Schema Design
- **Normalization**: Follow 3NF unless denormalization is required for performance.
- **Data Types**: Use appropriate types (e.g., `UUID` for IDs, `TIMESTAMPTZ` for dates, `JSONB` for flexible data).
- **Constraints**: Use `NOT NULL`, `UNIQUE`, and `CHECK` constraints to ensure data integrity at the database level.
- **Indexes**: Use `B-tree` for equality and range queries, `GIN` for JSONB/Arrays, and `BRIN` for large sequential datasets.

## 🛡 Security & Privacy
- **Row Level Security (RLS)**: Mandatory for all tables in Supabase. Define strict policies based on `auth.uid()`.
- **Encryption**: Use `pg_sodium` for sensitive data encryption.
- **Schemas**: Isolate data using different Postgres schemas (e.g., `public`, `private`, `auth`).
- **PII**: Avoid storing raw PII where possible. Use hashing or encryption for sensitive fields.

## 🚀 Performance & Optimization
- **EXPLAIN ANALYZE**: Always use to identify slow queries and sequential scans.
- **Vacuum & Analyze**: Monitor bloat and keep statistics up to date.
- **Connection Pooling**: Use `Supavisor` or `PgBouncer` for high-concurrency applications.
- **Pagination**: Prefer keyset pagination (cursor-based) over `OFFSET` for large datasets.

## ⚡ Supabase Features
- **Edge Functions**: Use for logic that requires external API calls or heavy processing. Use Deno/TypeScript.
- **Realtime**: Use sparingly for live updates. Filter channels to reduce overhead.
- **Storage**: Use for large assets. Enforce RLS on buckets and folders.
- **Migrations**: Use the Supabase CLI for declarative migrations. Never make manual changes in production.

## 🔗 References
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Supabase Documentation](https://supabase.com/docs)
- [Supabase RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)
