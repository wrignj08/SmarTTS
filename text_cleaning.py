import json
import logging
import re
from pathlib import Path
from typing import List, Union

import emoji
import inflect
from nltk.tokenize import sent_tokenize


def replace_long_numbers(text: str) -> str:
    p = inflect.engine()
    words = text.split()
    for i, word in enumerate(words):
        if word.isdigit() and len(word) > 3:
            words[i] = p.number_to_words(word)  # type: ignore
    return " ".join(words)


def load_replacement_rules(config_path: Union[str, Path]) -> List[List[str]]:
    """
    Load text replacement rules from a JSON configuration file.

    Args:
        config_path: Path to the JSON configuration file

    Returns:
        List of replacement rules, each containing [from_text, to_text]

    Raises:
        FileNotFoundError: If the config file doesn't exist
        json.JSONDecodeError: If the config file is not valid JSON
        KeyError: If the config file doesn't have the expected structure
    """
    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        if not isinstance(config, dict) or "replacements" not in config:
            raise KeyError("Config file must contain a 'replacements' key")

        rules = []
        for rule in config["replacements"]:
            if not isinstance(rule, dict) or "from" not in rule or "to" not in rule:
                raise KeyError("Each replacement rule must have 'from' and 'to' keys")
            rules.append([rule["from"], rule["to"]])

        return rules

    except FileNotFoundError:
        raise FileNotFoundError(f"Replacement rules file not found: {config_path}")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(
            "Error decoding JSON in replacement rules file", "", 0
        )


def clean_text(
    text: str, config_path: Union[str, Path] = "text_replacements.json"
) -> str:
    """
    Clean text by removing unwanted characters and standardizing formatting.

    Args:
        text: Input text to clean
        config_path: Path to the JSON configuration file containing replacement rules

    Returns:
        Cleaned text string
    """
    # Replace newlines with periods if they're followed by capital letters
    text = re.sub(r"\n(?=[A-Z])", ". ", text)

    # Normalize whitespace
    text = " ".join(text.split())

    try:
        # Load and apply replacement rules
        remove_chars = load_replacement_rules(config_path)
        for char in remove_chars:
            text = text.replace(char[0], char[1])

        return text

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logging.warning(f"Warning: Error loading replacement rules - {str(e)}")

        return text


def make_sentences(text: str) -> list[str]:

    text_chunks = sent_tokenize(text)
    for rm in ["\r", "\t", ".", " "]:
        if rm in text_chunks:
            text_chunks.remove(rm)

    text_chunks = [chunk.strip() for chunk in text_chunks]

    return text_chunks


def combined_text_cleaning(text: str) -> str:
    """Remove unwanted characters, replace long numbers with words, and replace emojis with text."""
    # Remove unwanted characters
    text = clean_text(text)

    # Replace long numbers with words
    text = replace_long_numbers(text)

    # Replace emojis with text
    text = emoji.demojize(text)

    return text
