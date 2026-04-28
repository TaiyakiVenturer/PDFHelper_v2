import { useNavigate } from "react-router-dom";
import { UploadDropZone } from "../components/UploadDropZone";

export function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="home-page">
      <UploadDropZone
        onUploadSuccess={() => void navigate("/files")}
        fullPage
      />
    </div>
  );
}
