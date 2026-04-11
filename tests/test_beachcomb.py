"""Tests for Beachcomb — scheduled scavenging system."""
import sys, os, tempfile, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from flux.open_interp.beachcomb import (
    Beachcomber, Sweep, SweepResult, SourceType, OnFind, Priority
)


class TestSweep:
    def test_create_sweep(self):
        s = Sweep(name="test", source_type=SourceType.GIT_FOLDER,
                  source="https://github.com/Lucineer/JetsonClaw1-vessel/message-in-a-bottle/for-oracle1/")
        assert s.name == "test"
        assert s.source_type == SourceType.GIT_FOLDER
        assert s.interval_minutes == 60
        assert s.on_find == OnFind.SILENT
    
    def test_is_due_initially(self):
        s = Sweep(name="test", source_type=SourceType.GIT_COMMITS,
                  source="https://github.com/foo/bar")
        # Never swept — should be due
        assert s.is_due()
    
    def test_is_due_after_sweep(self):
        s = Sweep(name="test", source_type=SourceType.GIT_COMMITS,
                  source="https://github.com/foo/bar", interval_minutes=60)
        s.last_sweep = time.time()
        assert not s.is_due()
    
    def test_is_due_inactive(self):
        s = Sweep(name="test", source_type=SourceType.GIT_COMMITS,
                  source="https://github.com/foo/bar", active=False)
        assert not s.is_due()
    
    def test_serialization(self):
        s = Sweep(name="test", source_type=SourceType.API_JSON,
                  source="https://api.example.com/data",
                  interval_minutes=30, on_find=OnFind.NOTIFY,
                  priority=Priority.HIGH, filter_pattern=r"urgent",
                  metadata={"headers": {"Auth": "Bearer xyz"}})
        d = s.to_dict()
        s2 = Sweep.from_dict(d)
        assert s2.name == "test"
        assert s2.source_type == SourceType.API_JSON
        assert s2.on_find == OnFind.NOTIFY
        assert s2.priority == Priority.HIGH
        assert s2.filter_pattern == r"urgent"
        assert s2.metadata["headers"]["Auth"] == "Bearer xyz"


class TestBeachcomber:
    def test_add_remove_sweep(self):
        bc = Beachcomber("oracle1")
        s = Sweep(name="test", source_type=SourceType.GIT_FOLDER, source="https://github.com/a/b/c")
        bc.add_sweep(s)
        assert "test" in bc.sweeps
        bc.remove_sweep("test")
        assert "test" not in bc.sweeps
    
    def test_update_sweep(self):
        bc = Beachcomber("oracle1")
        bc.add_sweep(Sweep(name="test", source_type=SourceType.GIT_COMMITS,
                          source="https://github.com/a/b", interval_minutes=60))
        bc.update_sweep("test", interval_minutes=15)
        assert bc.sweeps["test"].interval_minutes == 15
    
    def test_due_sweeps(self):
        bc = Beachcomber("oracle1")
        bc.add_sweep(Sweep(name="due", source_type=SourceType.GIT_COMMITS,
                          source="https://github.com/a/b"))
        bc.add_sweep(Sweep(name="not-due", source_type=SourceType.GIT_COMMITS,
                          source="https://github.com/a/b"))
        bc.sweeps["not-due"].last_sweep = time.time()
        due = bc.due_sweeps()
        assert "due" in due
        assert "not-due" not in due
    
    def test_status(self):
        bc = Beachcomber("oracle1")
        bc.add_sweep(Sweep(name="test", source_type=SourceType.GIT_COMMITS,
                          source="https://github.com/a/b", priority=Priority.HIGH))
        status = bc.status()
        assert status["agent"] == "oracle1"
        assert status["total_sweeps"] == 1
        assert status["sweeps"]["test"]["priority"] == "high"
    
    def test_save_load(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        
        bc = Beachcomber("oracle1")
        bc.add_sweep(Sweep(name="test", source_type=SourceType.GIT_COMMITS,
                          source="https://github.com/a/b", interval_minutes=30))
        bc.save(path)
        
        bc2 = Beachcomber("oracle1", config_path=path)
        assert "test" in bc2.sweeps
        assert bc2.sweeps["test"].interval_minutes == 30
        
        os.unlink(path)
    
    def test_nonexistent_sweep(self):
        bc = Beachcomber("oracle1")
        assert bc.sweep_one("nonexistent") is None
        assert not bc.update_sweep("nonexistent", interval_minutes=5)
        assert not bc.remove_sweep("nonexistent")


class TestSweepTypes:
    def test_all_source_types(self):
        types = [SourceType.GIT_FOLDER, SourceType.GIT_COMMITS, SourceType.GIT_ISSUES,
                 SourceType.GIT_PRS, SourceType.API_JSON, SourceType.RSS,
                 SourceType.STOCK, SourceType.CUSTOM]
        assert len(types) == 8
    
    def test_all_on_find(self):
        finds = [OnFind.NOTIFY, OnFind.COMMIT, OnFind.PR, OnFind.SILENT,
                 OnFind.BOTTLE, OnFind.TELL_ASSOCIATE]
        assert len(finds) == 6
    
    def test_all_priorities(self):
        prios = [Priority.URGENT, Priority.HIGH, Priority.MEDIUM,
                 Priority.LOW, Priority.BACKGROUND]
        assert len(prios) == 5


class TestOracle1DefaultSweeps:
    """Test the default sweep configuration Oracle1 would use."""
    
    def test_default_sweep_config(self):
        bc = Beachcomber("oracle1")
        
        # JetsonClaw1's bottles — check every 60 minutes
        bc.add_sweep(Sweep(
            name="jetsonclaw1-bottles",
            source_type=SourceType.GIT_FOLDER,
            source="https://github.com/Lucineer/JetsonClaw1-vessel/message-in-a-bottle/for-oracle1/",
            interval_minutes=60,
            on_find=OnFind.NOTIFY,
            notify_channel="telegram",
            priority=Priority.HIGH,
        ))
        
        # JetsonClaw1's commits — check every 15 minutes for I2I messages
        bc.add_sweep(Sweep(
            name="jetsonclaw1-commits",
            source_type=SourceType.GIT_COMMITS,
            source="https://github.com/Lucineer/JetsonClaw1-vessel",
            interval_minutes=15,
            on_find=OnFind.COMMIT,
            notify_channel="none",  # Casey reads the commit feed
            filter_pattern=r"\[I2I:",
        ))
        
        # JetsonClaw1's issues — check every 30 minutes
        bc.add_sweep(Sweep(
            name="jetsonclaw1-issues",
            source_type=SourceType.GIT_ISSUES,
            source="https://github.com/Lucineer/JetsonClaw1-vessel",
            interval_minutes=30,
            on_find=OnFind.SILENT,
            filter_pattern=r"\[I2I:",
        ))
        
        # Iron-to-iron changes — watch for protocol evolution
        bc.add_sweep(Sweep(
            name="i2i-protocol",
            source_type=SourceType.GIT_COMMITS,
            source="https://github.com/SuperInstance/iron-to-iron",
            interval_minutes=120,
            on_find=OnFind.SILENT,
            priority=Priority.LOW,
        ))
        
        assert len(bc.sweeps) == 4
        assert bc.sweeps["jetsonclaw1-bottles"].priority == Priority.HIGH
        assert bc.sweeps["jetsonclaw1-commits"].interval_minutes == 15
        assert bc.sweeps["jetsonclaw1-commits"].filter_pattern == r"\[I2I:"
        assert bc.sweeps["i2i-protocol"].interval_minutes == 120
        status = bc.status()
        assert status["total_sweeps"] == 4
        assert len(status["due_now"]) == 4
