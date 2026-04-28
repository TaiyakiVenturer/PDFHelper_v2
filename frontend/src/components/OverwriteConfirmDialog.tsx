import { ConfirmDialog } from "./ConfirmDialog";

interface OverwriteConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  onCancel: () => void;
  onConfirm: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
}

export function OverwriteConfirmDialog({
  open,
  title,
  message,
  onCancel,
  onConfirm,
  confirmLabel = "繼續覆寫",
  cancelLabel = "取消",
}: OverwriteConfirmDialogProps) {
  return (
    <ConfirmDialog
      open={open}
      title={title}
      message={message}
      confirmLabel={confirmLabel}
      cancelLabel={cancelLabel}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  );
}
