// Package security provides audit logging capabilities.
package security

import (
    "encoding/json"
    "os"
    "sync"
    "time"
)

// AuditEntry represents a single immutable audit record.
// The fields are deliberately simple for demonstration; in a real system they would be richer.
type AuditEntry struct {
    Timestamp time.Time `json:"timestamp"`
    UserID    string    `json:"user_id"`
    Action    string    `json:"action"`
    Resource  string    `json:"resource"`
    Details   string    `json:"details,omitempty"`
}

// Auditor provides an immutable append‑only audit log.
// It writes JSON lines to a file that is opened with O_APPEND and O_WRONLY
// and never truncates existing content.
type Auditor struct {
    mu   sync.Mutex
    file *os.File
}

// NewAuditor creates (or opens) an audit log file at the given path.
// The file is created if it does not exist and opened in append‑only mode.
func NewAuditor(path string) (*Auditor, error) {
    f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o600)
    if err != nil {
        return nil, err
    }
    return &Auditor{file: f}, nil
}

// Log records a new audit entry. The entry is marshaled as a single JSON line.
func (a *Auditor) Log(entry AuditEntry) error {
    a.mu.Lock()
    defer a.mu.Unlock()
    // Ensure timestamp is set
    if entry.Timestamp.IsZero() {
        entry.Timestamp = time.Now().UTC()
    }
    data, err := json.Marshal(entry)
    if err != nil {
        return err
    }
    // Append newline for line‑delimited JSON
    data = append(data, '\n')
    _, err = a.file.Write(data)
    return err
}

// Close releases the underlying file handle.
func (a *Auditor) Close() error {
    return a.file.Close()
}
