import { useState } from "react";

import { FileInfoPanel } from "../components/FileInfoPanel";
import { FileListPanel } from "../components/FileListPanel";
import type { PdfFileItem } from "../services/fileService";

export function FilesPage() {
  const [selectedFile, setSelectedFile] = useState<PdfFileItem | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleDeleteSuccess = () => {
    setSelectedFile(null);
    setRefreshKey((k) => k + 1);
  };

  return (
    <div className="files-page">
      <div className="files-page-left panel">
        <h2 className="panel-title">檔案列表</h2>
        <div className="files-list-scroll">
          <FileListPanel
            selectedCollection={selectedFile?.collection_name ?? null}
            onSelect={setSelectedFile}
            refreshTrigger={refreshKey}
          />
        </div>
      </div>
      <div className="files-page-right panel">
        <FileInfoPanel selectedFile={selectedFile} onDeleteSuccess={handleDeleteSuccess} />
      </div>
    </div>
  );
}
