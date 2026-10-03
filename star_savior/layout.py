"""Normalized event regions for the supplied landscape game layout."""

DEFAULT_REGIONS = {
    'title': (0.115, 0.155, 0.250, 0.230),
    'options': (0.655, 0.480, 0.995, 0.835),
}


def valid_regions(regions):
    if not isinstance(regions, dict) or set(regions) != {'title', 'options'}:
        return False
    for region in regions.values():
        if not isinstance(region, (list, tuple)) or len(region) != 4:
            return False
        if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in region):
            return False
        if region[0] >= region[2] or region[1] >= region[3]:
            return False
    return True


def crop_regions(image, regions):
    if not valid_regions(regions):
        raise ValueError('标题或选项识别区域无效。')
    return {name: image.crop((round(left * image.width), round(top * image.height),
                             round(right * image.width), round(bottom * image.height)))
            for name, (left, top, right, bottom) in regions.items()}
