from PIL import Image
import sys
import struct
import io

def create_multi_size_ico(input_path, output_path):
    """Создаёт настоящий многоразмерный ICO файл с несколькими изображениями"""
    try:
        # Открываем исходное изображение
        img = Image.open(input_path)
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Масштабируем до базового размера 256x256
        base_size = max(256, max(img.size))
        base_img = img.resize((base_size, base_size), Image.Resampling.LANCZOS)
        
        # Размеры для ICO
        sizes = [16, 24, 32, 48, 64, 128, 256]
        
        # Создаём изображения всех размеров
        images = []
        for size in sizes:
            resized = base_img.resize((size, size), Image.Resampling.LANCZOS)
            images.append(resized)
        
        # Формируем ICO файл вручную
        with open(output_path, 'wb') as f:
            # ICO Header: Reserved (2 bytes) + Type (2 bytes) + Count (2 bytes)
            f.write(struct.pack('<HHH', 0, 1, len(images)))
            
            # Offset для данных изображений (начало после всех directory entries)
            offset = 6 + (16 * len(images))
            
            # Image Directory Entries
            png_data_list = []
            for img in images:
                # Конвертируем в PNG для хранения внутри ICO
                png_buffer = io.BytesIO()
                img.save(png_buffer, format='PNG')
                png_data = png_buffer.getvalue()
                png_data_list.append(png_data)
                
                width = img.width if img.width < 256 else 0  # 0 означает 256
                height = img.height if img.height < 256 else 0
                
                # Directory Entry: Width (1) + Height (1) + ColorCount (1) + Reserved (1) +
                #                  Planes (2) + BitCount (2) + BytesInRes (4) + ImageOffset (4)
                f.write(struct.pack('<BBBBHHII',
                                  width, height, 0, 0,  # Width, Height, ColorCount, Reserved
                                  1, 32,                 # Planes, BitCount (32-bit RGBA)
                                  len(png_data),         # Size of image data
                                  offset))               # Offset to image data
                offset += len(png_data)
            
            # Записываем данные всех изображений
            for png_data in png_data_list:
                f.write(png_data)
        
        print(f"Multi-size ICO created: {len(sizes)} images ({', '.join(f'{s}x{s}' for s in sizes)})")
        return True
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python normalize_icon.py <icon_path>")
        sys.exit(1)
    
    icon_path = sys.argv[1]
    success = create_multi_size_ico(icon_path, icon_path)
    sys.exit(0 if success else 1)
