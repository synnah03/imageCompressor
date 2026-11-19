import argparse
import os
import shutil
from PIL import Image

# Use raw strings for Windows paths
input_folder = r"D:\python\reducedImage\before"
output_folder = r"D:\python\reducedImage\after"

# Target max file size for every output image
MAX_SIZE_BYTES = int(512 * 1024)  # 512Kb


def process_folder(input_folder, output_folder, quality=85, scale=None, width=None, height=None,
                    max_size_bytes=MAX_SIZE_BYTES):
    """Process all images in input folder and save compressed versions to output folder"""
    # Convert to absolute paths
    input_folder = os.path.abspath(input_folder)
    output_folder = os.path.abspath(output_folder)

    # Check if input folder exists
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return

    files = os.listdir(input_folder)
    print(f"Found {len(files)} items in input folder: {files}")

    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Supported image extensions
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')

    image_files = [f for f in files if f.lower().endswith(valid_extensions)]
    if not image_files:
        print("No supported image files found in the input folder.")
        return

    # Process each file in input folder
    for filename in image_files:
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        try:
            # Process individual image
            reduce_filesize(input_path, output_path, quality, scale, width, height, max_size_bytes)
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")


def reduce_filesize(input_path, output_path, quality=85, scale=None, width=None, height=None,
                     max_size_bytes=MAX_SIZE_BYTES):
    """Reduce image file size below max_size_bytes by adjusting quality and, if needed, resizing.
    If the original is already under the target (and no resize was requested), it is copied
    as-is instead of being needlessly re-encoded, since re-encoding can sometimes *increase*
    file size."""
    try:
        original_size = os.path.getsize(input_path)
        print(f"\nProcessing: {os.path.basename(input_path)}")
        print(f"Original size: {original_size / 1024:.2f} KB")

        # If the file is already small enough and no explicit resize was requested,
        # just copy it over untouched rather than risk re-encoding it larger.
        if original_size <= max_size_bytes and not (scale or width or height):
            shutil.copy2(input_path, output_path)
            print(f"Already under target ({max_size_bytes / 1024:.0f} KB) - copied without re-encoding.")
            return

        with Image.open(input_path) as original_img:
            img = original_img.copy()

            # Apply any explicit resize requested by the user first
            if scale or width or height:
                img = resize_image(img, scale, width, height)

            output_format = output_path.split('.')[-1].lower()

            # First attempt at requested quality
            save_image(img, output_path, output_format, quality)
            new_size = os.path.getsize(output_path)

            # If still above the target, iteratively reduce quality, then scale down
            current_quality = quality
            current_img = img

            while new_size > max_size_bytes:
                reduced = False

                # Step 1: lower quality (only helps for lossy formats: jpg/webp)
                if output_format in ('jpg', 'jpeg', 'webp') and current_quality > 20:
                    current_quality = max(20, current_quality - 10)
                    save_image(current_img, output_path, output_format, current_quality)
                    new_size = os.path.getsize(output_path)
                    reduced = True

                # Step 2: if quality is already at its floor (or format is lossless like PNG),
                # scale the image down instead
                if not reduced or new_size > max_size_bytes:
                    w, h = current_img.size
                    if w <= 100 or h <= 100:
                        # Safety floor so we don't shrink to nothing
                        break
                    current_img = current_img.resize(
                        (int(w * 0.85), int(h * 0.85)), Image.LANCZOS
                    )
                    save_image(current_img, output_path, output_format, current_quality)
                    new_size = os.path.getsize(output_path)

            # Safety net: if after all this the "compressed" output is still larger
            # than the original, just fall back to copying the original file instead.
            if new_size > original_size:
                shutil.copy2(input_path, output_path)
                new_size = original_size
                print("Re-encoded result was larger than original - copied original instead.")

            reduction = (original_size - new_size) / original_size * 100
            print(f"New size: {new_size / 1024:.2f} KB "
                  f"(quality={current_quality}, dimensions={current_img.size[0]}x{current_img.size[1]})")
            print(f"Reduction: {reduction:.1f}%")

            if new_size > max_size_bytes:
                print(f"Warning: could not get below {max_size_bytes / 1024 / 1024:.2f} MB "
                      f"without excessive downscaling.")

    except Exception as e:
        print(f"Error: {e}")


def resize_image(img, scale, width, height):
    """Resize image based on provided parameters"""
    orig_width, orig_height = img.size

    if scale:
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
    elif width and height:
        new_width, new_height = width, height
    elif width:
        ratio = width / orig_width
        new_width = width
        new_height = int(orig_height * ratio)
    elif height:
        ratio = height / orig_height
        new_height = height
        new_width = int(orig_width * ratio)
    else:
        return img  # No resizing needed

    # Avoid upscaling
    if new_width > orig_width or new_height > orig_height:
        print("Warning: Resizing would increase dimensions. Skipping resize.")
        return img

    print(f"Resizing to: {new_width}x{new_height}")
    return img.resize((new_width, new_height), Image.LANCZOS)


def save_image(img, output_path, output_format, quality):
    """Save image with format-specific optimizations"""
    if output_format in ['jpg', 'jpeg']:
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(output_path, format='JPEG', quality=quality, optimize=True)

    elif output_format == 'png':
        img.save(output_path, format='PNG', optimize=True)

    elif output_format == 'webp':
        if img.mode == 'RGBA' and not img.getchannel('A').getbbox():
            img = img.convert('RGB')
        img.save(output_path, format='WEBP', quality=quality, method=6)

    else:
        img.save(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Batch reduce image file sizes (target: under 1.5MB each)')
    parser.add_argument('input_folder', nargs='?', default=input_folder, help='Input folder path')
    parser.add_argument('output_folder', nargs='?', default=output_folder, help='Output folder path')
    parser.add_argument('--quality', type=int, default=85, help='Starting compression quality (1-100)')
    parser.add_argument('--scale', type=float, help='Resize scale factor (e.g., 0.5)')
    parser.add_argument('--width', type=int, help='Target width in pixels')
    parser.add_argument('--height', type=int, help='Target height in pixels')
    parser.add_argument('--max-size-mb', type=float, default=0.5, help='Maximum output file size in MB')

    args = parser.parse_args()

    print(f"Processing images from: {os.path.abspath(args.input_folder)}")
    print(f"Saving compressed images to: {os.path.abspath(args.output_folder)}")
    print(f"Target max size per image: {args.max_size_mb} MB")

    process_folder(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        quality=args.quality,
        scale=args.scale,
        width=args.width,
        height=args.height,
        max_size_bytes=int(args.max_size_mb * 1024 * 1024)
    )


