import os
from pathlib import Path

class GuardError(Exception):
    pass

class PathEscapeError(GuardError):
    pass

class SecurityGuards:
    @staticmethod
    def assert_safe_path(target_path: Path | str, approved_base: Path | str) -> None:
        """
        Validates target_path against approved_base.
        Normalizes paths, resolves directories (following symlinks/junctions),
        and verifies that target_path is relative to approved_base using Path.is_relative_to.
        Throws PathEscapeError if target_path is not inside approved_base.
        """
        target_path = Path(target_path)
        approved_base = Path(approved_base)
        
        # 1. Resolve approved_base
        if not approved_base.exists():
            raise PathEscapeError(f"Base path does not exist: {approved_base}")
        resolved_base = approved_base.resolve()
        
        # 2. Resolve target_path (handling non-existing targets securely)
        try:
            if target_path.exists() or os.path.islink(target_path):
                resolved_target = target_path.resolve()
            else:
                # If target does not exist, find the first existing parent and resolve it,
                # then append the non-existing parts to prevent traversal spoofing.
                parent = target_path.parent
                parts = [target_path.name]
                while not (parent.exists() or os.path.islink(parent)) and parent != parent.parent:
                    parts.insert(0, parent.name)
                    parent = parent.parent
                resolved_parent = parent.resolve()
                resolved_target = resolved_parent.joinpath(*parts)
        except Exception as e:
            raise PathEscapeError(f"Failed to resolve path {target_path}: {e}")
            
        # 3. Explicit check for parent traversal parts in original or resolved path
        if ".." in target_path.parts or ".." in resolved_target.parts:
            raise PathEscapeError(f"Directory traversal detected: {target_path}")
            
        # 4. Use Path.is_relative_to to assert the path resides in approved_base.
        # This prevents sibling-prefix escape (e.g. C:/base2 vs C:/base) naturally.
        try:
            is_sub = resolved_target.is_relative_to(resolved_base)
        except ValueError:
            is_sub = False
            
        if not is_sub:
            raise PathEscapeError(
                f"Path escape detected: {target_path} (resolved: {resolved_target}) "
                f"is not relative to approved base {approved_base} (resolved: {resolved_base})"
            )
