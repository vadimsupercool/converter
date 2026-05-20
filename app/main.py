from pathlib import Path, PureWindowsPath
import shutil
import uuid

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.converters import (
    convert_image,
    convert_audio,
    convert_pdf_to_docx,
    convert_docx_to_pdf,
    validate_image_file,
    compress_image,
    compress_audio
)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

app = FastAPI(title="Локальный конвертер файлов")

app.mount(
    "/static",
    StaticFiles(directory=PROJECT_DIR / "static"),
    name="static"
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")

UPLOAD_DIR = PROJECT_DIR / "uploads"
RESULT_DIR = PROJECT_DIR / "results"

UPLOAD_DIR.mkdir(exist_ok=True)
RESULT_DIR.mkdir(exist_ok=True)


ALLOWED_EXTENSIONS = {
    "jpg_to_png": [".jpg", ".jpeg"],
    "png_to_jpg": [".png"],
    "mp3_to_wav": [".mp3"],
    "wav_to_mp3": [".wav"],
    "pdf_to_docx": [".pdf"],
    "docx_to_pdf": [".docx"],
}

CONVERSION_NAMES = {
    "jpg_to_png": "JPG в PNG",
    "png_to_jpg": "PNG в JPG",
    "mp3_to_wav": "MP3 в WAV",
    "wav_to_mp3": "WAV в MP3",
    "pdf_to_docx": "PDF в DOCX",
    "docx_to_pdf": "DOCX в PDF",
}

OUTPUT_EXTENSIONS = {
    "jpg_to_png": ".png",
    "png_to_jpg": ".jpg",
    "mp3_to_wav": ".wav",
    "wav_to_mp3": ".mp3",
    "pdf_to_docx": ".docx",
    "docx_to_pdf": ".pdf",
}

COMPRESSION_ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".mp3", ".wav"]

COMPRESSION_QUALITY_NAMES = {
    "high": "Высокое качество",
    "medium": "Среднее качество",
    "low": "Максимальное сжатие"
}

MAX_FILE_SIZE = 50 * 1024 * 1024


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


def error_page(request: Request, message: str):
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"message": message},
        status_code=400
    )


def is_image_conversion(conversion_type: str) -> bool:
    return conversion_type in ["jpg_to_png", "png_to_jpg"]


def get_safe_filename(filename: str) -> str:
    """
    Получает безопасное имя файла без пути.
    Например:
    C:\\files\\voice.mp3 -> voice.mp3
    """
    windows_name = PureWindowsPath(filename).name
    safe_name = Path(windows_name).name

    return safe_name


def get_output_filename(original_filename: str, conversion_type: str) -> str:
    """
    Сохраняет исходное имя файла, но меняет расширение.
    Например:
    voice.mp3 -> voice.wav
    picture.png -> picture.jpg
    """
    original_stem = Path(original_filename).stem
    output_extension = OUTPUT_EXTENSIONS[conversion_type]

    return f"{original_stem}{output_extension}"


def get_allowed_formats_text(conversion_type: str) -> str:
    return ", ".join(ALLOWED_EXTENSIONS[conversion_type])


def is_compressible_image(file_suffix: str) -> bool:
    return file_suffix in [".jpg", ".jpeg", ".png"]


def is_compressible_audio(file_suffix: str) -> bool:
    return file_suffix in [".mp3", ".wav"]


def get_compressed_output_filename(original_filename: str, original_suffix: str) -> str:
    """
    Для изображений сохраняем исходный формат.
    Для MP3 сохраняем MP3.
    Для WAV создаем MP3, так как WAV сам по себе несжатый формат.
    """
    original_stem = Path(original_filename).stem

    if original_suffix == ".wav":
        return f"{original_stem}_compressed.mp3"

    return f"{original_stem}_compressed{original_suffix}"


@app.post("/convert")
async def convert_file(
    request: Request,
    file: UploadFile = File(...),
    conversion_type: str = Form(...)
):
    if conversion_type not in ALLOWED_EXTENSIONS:
        return error_page(
            request,
            "Неизвестный тип конвертации."
        )

    if not file.filename:
        return error_page(
            request,
            "Файл не выбран. Пожалуйста, выберите файл для конвертации."
        )

    original_filename = get_safe_filename(file.filename)
    original_suffix = Path(original_filename).suffix.lower()

    if not original_suffix:
        return error_page(
            request,
            "Неправильный формат файла. У файла отсутствует расширение."
        )

    allowed_extensions = ALLOWED_EXTENSIONS[conversion_type]

    if original_suffix not in allowed_extensions:
        conversion_name = CONVERSION_NAMES[conversion_type]
        allowed_formats = get_allowed_formats_text(conversion_type)

        return error_page(
            request,
            f"Неправильный формат файла. Для операции «{conversion_name}» разрешены только: {allowed_formats}."
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size == 0:
        return error_page(
            request,
            "Файл пустой. Выберите другой файл."
        )

    if file_size > MAX_FILE_SIZE:
        return error_page(
            request,
            "Размер файла превышает допустимый лимит 50 МБ."
        )

    job_id = str(uuid.uuid4())

    upload_job_dir = UPLOAD_DIR / job_id
    result_job_dir = RESULT_DIR / job_id

    upload_job_dir.mkdir(exist_ok=True)
    result_job_dir.mkdir(exist_ok=True)

    input_path = upload_job_dir / original_filename

    output_filename = get_output_filename(original_filename, conversion_type)
    output_path = result_job_dir / output_filename

    try:
        with input_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if is_image_conversion(conversion_type):
            if not validate_image_file(input_path):
                return error_page(
                    request,
                    "Неправильный формат файла. Загруженный файл не является корректным изображением."
                )

        if conversion_type == "jpg_to_png":
            convert_image(input_path, output_path)

        elif conversion_type == "png_to_jpg":
            convert_image(input_path, output_path)

        elif conversion_type == "mp3_to_wav":
            convert_audio(input_path, output_path)

        elif conversion_type == "wav_to_mp3":
            convert_audio(input_path, output_path)

        elif conversion_type == "pdf_to_docx":
            convert_pdf_to_docx(input_path, output_path)

        elif conversion_type == "docx_to_pdf":
            convert_docx_to_pdf(input_path, output_path)

    except FileNotFoundError as error:
        return error_page(
            request,
            str(error)
        )

    except Exception:
        return error_page(
            request,
            "Во время конвертации произошла ошибка. Проверьте файл и попробуйте снова."
        )

    finally:
        if input_path.exists():
            input_path.unlink()

        if upload_job_dir.exists():
            try:
                upload_job_dir.rmdir()
            except OSError:
                pass

    if not output_path.exists():
        return error_page(
            request,
            "Файл не был создан. Проверьте настройки конвертации."
        )

    return FileResponse(
        path=output_path,
        filename=output_filename,
        media_type="application/octet-stream"
    )


@app.post("/compress")
async def compress_file(
    request: Request,
    file: UploadFile = File(...),
    quality: str = Form(...)
):
    if quality not in COMPRESSION_QUALITY_NAMES:
        return error_page(
            request,
            "Некорректно выбрано качество сжатия."
        )

    if not file.filename:
        return error_page(
            request,
            "Файл не выбран. Пожалуйста, выберите файл для сжатия."
        )

    original_filename = get_safe_filename(file.filename)
    original_suffix = Path(original_filename).suffix.lower()

    if not original_suffix:
        return error_page(
            request,
            "Неправильный формат файла. У файла отсутствует расширение."
        )

    if original_suffix not in COMPRESSION_ALLOWED_EXTENSIONS:
        return error_page(
            request,
            "Неподдерживаемый формат файла для сжатия. Разрешены: JPG, JPEG, PNG, MP3, WAV."
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size == 0:
        return error_page(
            request,
            "Файл пустой. Выберите другой файл."
        )

    if file_size > MAX_FILE_SIZE:
        return error_page(
            request,
            "Размер файла превышает допустимый лимит 50 МБ."
        )

    job_id = str(uuid.uuid4())

    upload_job_dir = UPLOAD_DIR / job_id
    result_job_dir = RESULT_DIR / job_id

    upload_job_dir.mkdir(exist_ok=True)
    result_job_dir.mkdir(exist_ok=True)

    input_path = upload_job_dir / original_filename

    output_filename = get_compressed_output_filename(
        original_filename,
        original_suffix
    )
    output_path = result_job_dir / output_filename

    try:
        with input_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if is_compressible_image(original_suffix):
            if not validate_image_file(input_path):
                return error_page(
                    request,
                    "Неправильный формат файла. Загруженный файл не является корректным изображением."
                )

            compress_image(input_path, output_path, quality)

        elif is_compressible_audio(original_suffix):
            compress_audio(input_path, output_path, quality)

    except FileNotFoundError as error:
        return error_page(
            request,
            str(error)
        )

    except ValueError as error:
        return error_page(
            request,
            str(error)
        )

    except Exception:
        return error_page(
            request,
            "Во время сжатия произошла ошибка. Проверьте файл и попробуйте снова."
        )

    finally:
        if input_path.exists():
            input_path.unlink()

        if upload_job_dir.exists():
            try:
                upload_job_dir.rmdir()
            except OSError:
                pass

    if not output_path.exists():
        return error_page(
            request,
            "Сжатый файл не был создан. Проверьте настройки сжатия."
        )

    return FileResponse(
        path=output_path,
        filename=output_filename,
        media_type="application/octet-stream"
    )