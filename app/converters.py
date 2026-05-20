from pathlib import Path
import subprocess
import shutil

from PIL import Image, UnidentifiedImageError
from pdf2docx import Converter


#SOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"


def validate_image_file(input_path: Path) -> bool:
    try:
        with Image.open(input_path) as img:
            img.verify()

        return True

    except (UnidentifiedImageError, OSError):
        return False


def convert_image(input_path: Path, output_path: Path):
    try:
        with Image.open(input_path) as img:
            if output_path.suffix.lower() in [".jpg", ".jpeg"]:
                img = img.convert("RGB")

            img.save(output_path)

    except UnidentifiedImageError:
        raise ValueError("Файл не является корректным изображением.")


def convert_audio(input_path: Path, output_path: Path):
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError(
            "FFmpeg не найден. Установите FFmpeg и добавьте его в PATH."
        )

    command = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        str(output_path)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def convert_pdf_to_docx(input_path: Path, output_path: Path):
    converter = None

    try:
        converter = Converter(str(input_path))
        converter.convert(str(output_path))

    finally:
        if converter is not None:
            converter.close()


def convert_docx_to_pdf(input_path: Path, output_path: Path):
    soffice = shutil.which("libreoffice") or shutil.which("soffice")

    if not soffice:
        raise FileNotFoundError(
            "LibreOffice не найден. Установите LibreOffice на сервере."
        )

    output_dir = output_path.parent

    command = [
        soffice,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", str(output_dir),
        str(input_path)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    generated_pdf = output_dir / f"{input_path.stem}.pdf"

    if generated_pdf.exists() and generated_pdf != output_path:
        shutil.move(str(generated_pdf), str(output_path))
    
def compress_image(input_path: Path, output_path: Path, quality: str):
    """
    Сжатие изображений с выбором качества.
    Поддерживает JPG, JPEG, PNG.
    """

    quality_settings = {
        "high": 85,
        "medium": 65,
        "low": 40
    }

    if quality not in quality_settings:
        raise ValueError("Некорректное качество сжатия.")

    image_quality = quality_settings[quality]

    try:
        with Image.open(input_path) as img:
            output_suffix = output_path.suffix.lower()

            if output_suffix in [".jpg", ".jpeg"]:
                img = img.convert("RGB")
                img.save(
                    output_path,
                    quality=image_quality,
                    optimize=True
                )

            elif output_suffix == ".png":
                img.save(
                    output_path,
                    optimize=True,
                    compress_level=9
                )

            else:
                raise ValueError("Неподдерживаемый формат изображения для сжатия.")

    except UnidentifiedImageError:
        raise ValueError("Файл не является корректным изображением.")


def compress_audio(input_path: Path, output_path: Path, quality: str):
    """
    Сжатие аудио через FFmpeg.
    MP3 остается MP3, WAV сжимается в MP3.
    """

    if not shutil.which("ffmpeg"):
        raise FileNotFoundError(
            "FFmpeg не найден. Установите FFmpeg и добавьте его в PATH."
        )

    bitrate_settings = {
        "high": "192k",
        "medium": "128k",
        "low": "64k"
    }

    if quality not in bitrate_settings:
        raise ValueError("Некорректное качество сжатия.")

    command = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-b:a", bitrate_settings[quality],
        str(output_path)
    ]

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )