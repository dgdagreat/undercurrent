import { useRef, useState } from "react";
import { uploadBusiness } from "../api";

// Build a realistic 24-month sample CSV client-side so demo viewers always
// have a file to try: seasonal summer revenue, fixed rent, variable labor,
// and a monthly loan payment (which exercises the keyword classifier).
function sampleCsv() {
  const rows = ["date,description,amount"];
  const season = [0.2, 0.2, 0.5, 0.9, 1.3, 1.6, 1.8, 1.6, 1.1, 0.7, 0.4, 0.25];
  const now = new Date();
  for (let i = 23; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const rev = Math.round(52000 * season[d.getMonth()]);
    if (rev > 0) {
      rows.push(`${y}-${m}-08,Customer payments,${Math.round(rev * 0.55)}`);
      rows.push(`${y}-${m}-21,Customer payments,${Math.round(rev * 0.45)}`);
    }
    rows.push(`${y}-${m}-01,Warehouse rent,-6000`);
    rows.push(`${y}-${m}-15,Seasonal crew payroll,${-Math.round(rev * 0.45)}`);
    rows.push(`${y}-${m}-05,SBA loan payment,-1800`);
  }
  return rows.join("\n");
}

function downloadSample() {
  const blob = new Blob([sampleCsv()], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "sample-transactions.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// Modal for uploading a transactions CSV. Calls onDone(newBusiness) on success.
export default function UploadPanel({ onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [openingBalance, setOpeningBalance] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const pickFile = (f) => {
    if (f) setFile(f);
    setError(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!file) return setError("Choose a CSV file first.");
    if (!name.trim()) return setError("Give the business a name.");
    setBusy(true);
    setError(null);
    try {
      const biz = await uploadBusiness({
        file,
        name: name.trim(),
        industry: industry.trim(),
        openingBalance,
      });
      onDone(biz);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__head">
          <h2>Upload your business</h2>
          <button className="modal__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="modal__sub">
          Drop in a transactions CSV — a bank-statement download or accounting
          export works. Needs a <b>date</b> column and a signed <b>amount</b>{" "}
          column (positive&nbsp;=&nbsp;money in); description and category are
          optional but improve the analysis.{" "}
          <button type="button" className="linklike" onClick={downloadSample}>
            Download a sample CSV
          </button>
        </p>

        <form onSubmit={submit}>
          <div
            className={`dropzone${dragOver ? " dropzone--over" : ""}${
              file ? " dropzone--filled" : ""
            }`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              pickFile(e.dataTransfer.files?.[0]);
            }}
          >
            {file ? (
              <>
                <b>{file.name}</b>
                <span>{(file.size / 1024).toFixed(1)} KB — click to change</span>
              </>
            ) : (
              <>
                <b>Drag & drop a CSV here</b>
                <span>or click to browse</span>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept=".csv,text/csv"
              hidden
              onChange={(e) => pickFile(e.target.files?.[0])}
            />
          </div>

          <div className="form-grid">
            <label>
              Business name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Riverbend Rentals"
                maxLength={80}
              />
            </label>
            <label>
              Industry <em>(optional)</em>
              <input
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="e.g. Equipment Rental"
                maxLength={60}
              />
            </label>
            <label>
              Starting cash balance <em>(optional)</em>
              <input
                type="number"
                step="any"
                value={openingBalance}
                onChange={(e) => setOpeningBalance(e.target.value)}
                placeholder="e.g. 50000"
              />
            </label>
          </div>

          {error && <div className="form-error">{error}</div>}

          <div className="modal__actions">
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {busy ? "Scoring…" : "Upload & score"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
