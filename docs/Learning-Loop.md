# 🎓 The Self-Learning Feedback Loop

One of NulkaCLI's most powerful features is its ability to *permanently learn from its mistakes*.

## How it works

When you submit a query, and the responding agent provides an incomplete or factually incorrect response, you can immediately type:
```bash
/teach
```

This interrupts standard execution and triggers the **Feedback Loop**:
1. The **Teacher Agent** receives your previous query.
2. It bypasses the local models entirely and directly queries the **Universal Oracle** via the command line to fetch the absolute truth.
3. The CLI halts and presents you with a stylized interactive prompt, proposing a new "Lesson Learned" rule based on the Oracle's answer.
4. You can choose to Accept, Reject, or augment the rule by typing a custom response.

## Persistent Memory
Once approved, the rule is structurally appended to the bottom of the failing agent's Markdown backstory file under a `### 🎓 Learned Rules & Guidelines` header.

Because NulkaCLI dynamically loads these files at runtime, the agent permanently retains this knowledge and will apply it to all future sessions automatically!

### Viewing Learned Rules (`/memory`)
At any point during your session, you can type `/memory`. This will print the active compressed session memory, along with a full readout of all the global rules your agents have learned via the teaching loop so far.

### Reverting Mistakes (`/rewind`)
If a local agent hallucinates badly, messes up the context, and destroys a file before you had a chance to teach it, don't panic.
Type `/rewind`:
1. It pops the last turn out of the active session memory.
2. It automatically scans your workspace for timestamped `.bak` files generated in the last hour.
3. It interactively offers to restore those files back to their pristine state, giving the agent a clean slate for its next attempt.
