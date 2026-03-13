"""Document processor — chunking and embeddings for knowledge base."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

import openai

from mascarade.config import is_secret_configured, settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Processeur de documents avec chunking et génération d'embeddings."""

    def __init__(
        self,
        *,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "text-embedding-3-small",
        embedding_dimensions: int = 1536,
    ) -> None:
        """
        Initialiser le processeur de documents.

        Args:
            chunk_size: Taille maximale d'un chunk en caractères
            chunk_overlap: Chevauchement entre chunks en caractères
            embedding_model: Modèle OpenAI pour les embeddings
            embedding_dimensions: Dimensions du vecteur d'embedding
        """
        self._chunk_size = max(100, chunk_size)
        self._chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))
        self._embedding_model = embedding_model
        self._embedding_dimensions = embedding_dimensions
        self._openai_client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
        )

    @property
    def is_configured(self) -> bool:
        """Vérifie si OpenAI est configuré pour les embeddings."""
        return is_secret_configured(settings.openai_api_key)

    # --- Chunking ---

    def chunk_text(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Découper un texte en chunks avec métadonnées.

        Args:
            text: Texte à découper
            metadata: Métadonnées à ajouter à chaque chunk

        Returns:
            Liste de chunks avec métadonnées
        """
        if not text.strip():
            return []

        # Nettoyer le texte
        normalized = self._normalize_text(text)

        # Découper par paragraphes d'abord
        paragraphs = self._split_into_paragraphs(normalized)

        chunks: list[dict[str, Any]] = []
        current_chunk = ""
        current_position = 0

        for paragraph in paragraphs:
            # Si le paragraphe seul dépasse la taille max, le découper
            if len(paragraph) > self._chunk_size:
                # Sauvegarder le chunk actuel si non vide
                if current_chunk.strip():
                    chunks.append(
                        self._create_chunk(
                            current_chunk, current_position, metadata
                        )
                    )
                    current_position += len(current_chunk) - self._chunk_overlap
                    current_chunk = ""

                # Découper le long paragraphe
                sub_chunks = self._split_long_text(paragraph)
                for sub_chunk in sub_chunks:
                    chunks.append(
                        self._create_chunk(
                            sub_chunk, current_position, metadata
                        )
                    )
                    current_position += len(sub_chunk) - self._chunk_overlap

            # Si ajouter ce paragraphe dépasse la taille, sauvegarder le chunk actuel
            elif len(current_chunk) + len(paragraph) + 2 > self._chunk_size:
                if current_chunk.strip():
                    chunks.append(
                        self._create_chunk(
                            current_chunk, current_position, metadata
                        )
                    )
                    # Calculer le chevauchement
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_position += len(current_chunk) - len(overlap_text)
                    current_chunk = overlap_text + "\n\n" + paragraph if overlap_text else paragraph
                else:
                    current_chunk = paragraph

            # Sinon, ajouter le paragraphe au chunk actuel
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # Ajouter le dernier chunk
        if current_chunk.strip():
            chunks.append(
                self._create_chunk(current_chunk, current_position, metadata)
            )

        return chunks

    def _normalize_text(self, text: str) -> str:
        """Normaliser le texte (espaces, lignes vides)."""
        # Remplacer les multiples espaces par un seul
        text = re.sub(r"[ \t]+", " ", text)
        # Remplacer les multiples lignes vides par deux sauts de ligne
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        return text.strip()

    def _split_into_paragraphs(self, text: str) -> list[str]:
        """Découper le texte en paragraphes."""
        paragraphs = text.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]

    def _split_long_text(self, text: str) -> list[str]:
        """Découper un texte long en morceaux de taille appropriée."""
        chunks: list[str] = []
        current_pos = 0

        while current_pos < len(text):
            # Extraire un morceau
            end_pos = current_pos + self._chunk_size

            # Si ce n'est pas le dernier morceau, essayer de couper à un espace
            if end_pos < len(text):
                # Chercher le dernier espace dans la fenêtre
                last_space = text.rfind(" ", current_pos, end_pos)
                if last_space > current_pos:
                    end_pos = last_space

            chunk = text[current_pos:end_pos].strip()
            if chunk:
                chunks.append(chunk)

            # Avancer avec chevauchement
            current_pos = end_pos - self._chunk_overlap
            if current_pos <= current_pos:
                current_pos = end_pos

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """Obtenir le texte de chevauchement depuis la fin d'un chunk."""
        if len(text) <= self._chunk_overlap:
            return text
        return text[-self._chunk_overlap:].strip()

    def _create_chunk(
        self,
        text: str,
        position: int,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Créer un chunk avec métadonnées."""
        chunk_id = self._generate_chunk_id(text, position)
        chunk = {
            "id": chunk_id,
            "text": text.strip(),
            "position": position,
            "length": len(text),
        }
        if metadata:
            chunk["metadata"] = metadata.copy()
        return chunk

    @staticmethod
    def _generate_chunk_id(text: str, position: int) -> str:
        """Générer un ID unique pour un chunk."""
        content = f"{text}:{position}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    # --- Embeddings ---

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Générer un embedding pour un texte.

        Args:
            text: Texte à encoder

        Returns:
            Vecteur d'embedding
        """
        if not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        response = await self._openai_client.embeddings.create(
            model=self._embedding_model,
            input=text.strip(),
            dimensions=self._embedding_dimensions,
        )
        return response.data[0].embedding

    async def generate_embeddings_batch(
        self, texts: list[str]
    ) -> list[list[float]]:
        """
        Générer des embeddings pour plusieurs textes (batch).

        Args:
            texts: Liste de textes à encoder

        Returns:
            Liste de vecteurs d'embedding
        """
        if not texts:
            return []

        # Filtrer les textes vides
        valid_texts = [t.strip() for t in texts if t.strip()]
        if not valid_texts:
            return []

        response = await self._openai_client.embeddings.create(
            model=self._embedding_model,
            input=valid_texts,
            dimensions=self._embedding_dimensions,
        )

        # Extraire les embeddings dans l'ordre
        embeddings = [item.embedding for item in response.data]
        return embeddings

    async def process_document(
        self,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
        generate_embeddings: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Traiter un document complet: chunking + embeddings.

        Args:
            text: Texte du document
            metadata: Métadonnées du document
            generate_embeddings: Générer les embeddings pour chaque chunk

        Returns:
            Liste de chunks avec embeddings
        """
        # Découper en chunks
        chunks = self.chunk_text(text, metadata=metadata)

        if not chunks:
            return []

        # Générer les embeddings si demandé
        if generate_embeddings:
            if not self.is_configured:
                logger.warning(
                    "OpenAI non configuré, embeddings non générés"
                )
                return chunks

            # Extraire les textes
            texts = [chunk["text"] for chunk in chunks]

            try:
                # Générer les embeddings en batch
                embeddings = await self.generate_embeddings_batch(texts)

                # Ajouter les embeddings aux chunks
                for chunk, embedding in zip(chunks, embeddings):
                    chunk["embedding"] = embedding

            except Exception as e:
                logger.error(f"Erreur génération embeddings: {e}")
                # Retourner les chunks sans embeddings plutôt que d'échouer
                return chunks

        return chunks

    # --- Utilitaires ---

    def get_embedding_dimensions(self) -> int:
        """Obtenir les dimensions du vecteur d'embedding."""
        return self._embedding_dimensions

    def get_chunk_size(self) -> int:
        """Obtenir la taille des chunks."""
        return self._chunk_size

    def get_chunk_overlap(self) -> int:
        """Obtenir le chevauchement des chunks."""
        return self._chunk_overlap

    async def close(self) -> None:
        """Fermer les connexions."""
        await self._openai_client.close()
