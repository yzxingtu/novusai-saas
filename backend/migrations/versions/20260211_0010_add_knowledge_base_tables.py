"""add knowledge base tables

Revision ID: 20260211_0010
Revises: ee87f790553e
Create Date: 2026-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260211_0010'
down_revision: Union[str, None] = 'ee87f790553e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # 1. 启用 pgvector 扩展
    op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS vector'))

    # 2. 创建 knowledge_bases 表
    op.create_table('knowledge_bases',
        sa.Column('name', sa.String(length=200), nullable=False, comment='知识库名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('avatar', sa.String(length=50), nullable=True, comment='图标/颜色标识'),
        sa.Column('embedding_model_id', sa.Integer(), nullable=False, comment='Embedding 模型 ID'),
        sa.Column('embedding_dimensions', sa.Integer(), nullable=False, server_default='1536', comment='向量维度'),
        sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='512', comment='分块大小'),
        sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='50', comment='分块重叠'),
        sa.Column('chunk_strategy', sa.String(length=20), nullable=False, server_default='recursive', comment='分块策略'),
        sa.Column('search_mode', sa.String(length=20), nullable=False, server_default='hybrid', comment='检索模式'),
        sa.Column('top_k', sa.Integer(), nullable=False, server_default='5', comment='默认返回数量'),
        sa.Column('score_threshold', sa.Float(), nullable=False, server_default='0.5', comment='最低相似度阈值'),
        sa.Column('document_count', sa.Integer(), nullable=False, server_default='0', comment='文档总数'),
        sa.Column('total_chunks', sa.Integer(), nullable=False, server_default='0', comment='分块总数'),
        sa.Column('total_size_bytes', sa.Integer(), nullable=False, server_default='0', comment='原始文件总大小'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active', comment='状态'),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业ID'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false', comment='软删除标记'),
        sa.ForeignKeyConstraint(['embedding_model_id'], ['ai_models.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_knowledge_bases_id'), 'knowledge_bases', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_name'), 'knowledge_bases', ['name'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_embedding_model_id'), 'knowledge_bases', ['embedding_model_id'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_status'), 'knowledge_bases', ['status'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_tenant_id'), 'knowledge_bases', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_knowledge_bases_is_deleted'), 'knowledge_bases', ['is_deleted'], unique=False)
    op.create_index('ix_kb_tenant_status', 'knowledge_bases', ['tenant_id', 'status'], unique=False)

    # 3. 创建 knowledge_documents 表
    op.create_table('knowledge_documents',
        sa.Column('knowledge_base_id', sa.Integer(), nullable=False, comment='知识库 ID'),
        sa.Column('attachment_id', sa.Integer(), nullable=True, comment='附件 ID'),
        sa.Column('file_name', sa.String(length=500), nullable=False, comment='原始文件名'),
        sa.Column('file_type', sa.String(length=20), nullable=False, server_default='txt', comment='文件类型'),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0', comment='文件大小（字节）'),
        sa.Column('file_hash', sa.String(length=64), nullable=True, comment='MD5 哈希'),
        sa.Column('source_url', sa.Text(), nullable=True, comment='网页来源 URL'),
        sa.Column('metadata_extra', sa.Text(), nullable=True, comment='扩展元数据'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='处理状态'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('error_stage', sa.String(length=20), nullable=True, comment='失败阶段'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0', comment='重试次数'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0', comment='分块数量'),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0', comment='文档总 Token 数'),
        sa.Column('char_count', sa.Integer(), nullable=False, server_default='0', comment='文档总字符数'),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True, comment='处理开始时间'),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True, comment='处理完成时间'),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业ID'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false', comment='软删除标记'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('knowledge_base_id', 'file_hash', name='uq_doc_kb_hash'),
    )
    op.create_index(op.f('ix_knowledge_documents_id'), 'knowledge_documents', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_knowledge_base_id'), 'knowledge_documents', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_status'), 'knowledge_documents', ['status'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_tenant_id'), 'knowledge_documents', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_knowledge_documents_is_deleted'), 'knowledge_documents', ['is_deleted'], unique=False)
    op.create_index('ix_doc_kb_status', 'knowledge_documents', ['knowledge_base_id', 'status'], unique=False)

    # 4. 创建 document_chunks 表（含 pgvector Vector 列）
    op.create_table('document_chunks',
        sa.Column('document_id', sa.Integer(), nullable=False, comment='文档 ID'),
        sa.Column('knowledge_base_id', sa.Integer(), nullable=False, comment='知识库 ID'),
        sa.Column('chunk_index', sa.Integer(), nullable=False, comment='块序号'),
        sa.Column('content', sa.Text(), nullable=False, comment='分块文本内容'),
        sa.Column('content_hash', sa.String(length=64), nullable=False, comment='内容 MD5'),
        sa.Column('char_count', sa.Integer(), nullable=False, server_default='0', comment='字符数'),
        sa.Column('token_count', sa.Integer(), nullable=False, server_default='0', comment='Token 数'),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='元数据'),
        sa.Column('tenant_id', sa.Integer(), nullable=False, comment='企业ID'),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false', comment='软删除标记'),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'chunk_index', name='uq_doc_chunk_index'),
    )
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index('ix_chunk_kb', 'document_chunks', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_tenant_id'), 'document_chunks', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_is_deleted'), 'document_chunks', ['is_deleted'], unique=False)

    # 5. 添加 pgvector 向量列（需要 raw SQL，因为 alembic op 不直接支持 Vector 类型）
    op.execute(sa.text('ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)'))

    # 6. 创建 HNSW 向量索引
    op.execute(sa.text("""
        CREATE INDEX ix_chunk_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """))

    # 7. 创建 tsvector 生成列和 GIN 索引（用于关键词检索）
    op.execute(sa.text("""
        ALTER TABLE document_chunks
        ADD COLUMN content_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
    """))
    op.execute(sa.text('CREATE INDEX ix_chunk_tsv ON document_chunks USING GIN (content_tsv)'))

    # 8. Agent 表新增 rag_config 字段
    op.add_column('agents', sa.Column('rag_config', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='RAG 配置'))


def downgrade() -> None:
    """Downgrade database schema."""
    # 8. 移除 Agent RAG 字段
    op.drop_column('agents', 'rag_config')

    # 7. 删除 tsvector 索引和列
    op.execute(sa.text('DROP INDEX IF EXISTS ix_chunk_tsv'))
    op.execute(sa.text('ALTER TABLE document_chunks DROP COLUMN IF EXISTS content_tsv'))

    # 6. 删除 HNSW 索引
    op.execute(sa.text('DROP INDEX IF EXISTS ix_chunk_embedding'))

    # 5. 删除向量列
    op.execute(sa.text('ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding'))

    # 4. 删除 document_chunks 表
    op.drop_table('document_chunks')

    # 3. 删除 knowledge_documents 表
    op.drop_table('knowledge_documents')

    # 2. 删除 knowledge_bases 表
    op.drop_table('knowledge_bases')

    # 1. 注意：不删除 pgvector 扩展（其他迁移可能依赖）
