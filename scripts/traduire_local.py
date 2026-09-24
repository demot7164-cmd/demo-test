#!/usr/bin/env python3
"""
Script local pour traduire un DOCX sans worker.
Utilise le même moteur que le workflow.

Usage:
    python scripts/traduire_local.py <fichier.docx> <langue>

Exemple:
    python scripts/traduire_local.py document.docx fr
"""

import asyncio
import io
import sys
from pathlib import Path

# Import local modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.workflows.activities import (
    extract_text_with_runs,
    translate_with_mistral,
    replace_text_in_docx,
)


async def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/traduire_local.py <fichier.docx> <langue>")
        print("Langues supportées: en, es, de, it, pt, ru, zh, ja, ar, hi")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    target_language = sys.argv[2]
    
    if not input_file.exists():
        print(f"Erreur: Le fichier {input_file} n'existe pas")
        sys.exit(1)
    
    # Lire le fichier DOCX
    with open(input_file, 'rb') as f:
        docx_bytes = f.read()
    
    print(f"Lecture du fichier: {input_file}")
    
    # Extraire le texte avec les runs
    print("Extraction du texte avec les runs...")
    elements = await extract_text_with_runs(docx_bytes)
    print(f"Nombre d'éléments extraits: {len(elements)}")
    
    # Traduire avec Mistral
    print(f"Traduction vers {target_language}...")
    translated_elements = await translate_with_mistral(elements, target_language)
    print(f"Nombre d'éléments traduits: {len(translated_elements)}")
    
    # Remplacer le texte dans le DOCX
    print("Remplacement du texte dans le DOCX...")
    translated_docx_bytes = await replace_text_in_docx(docx_bytes, translated_elements)
    
    # Sauvegarder le résultat
    output_file = input_file.parent / f"translated_{target_language}_{input_file.name}"
    with open(output_file, 'wb') as f:
        f.write(translated_docx_bytes)
    
    print(f"Fichier traduit sauvegardé: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
