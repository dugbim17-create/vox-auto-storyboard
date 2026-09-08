import pytest
from app.services.quiz_episode_editor import record_observation

@pytest.mark.parametrize('updates',[{'views':-1},{'views':float('nan')},{'video_id':''},{'ctr':101}])
def test_invalid_measurement_never_written(tmp_path,updates):
    row=dict(channel_profile='de-football',video_id='v',period='7d',views=100)
    row.update(updates)
    path=tmp_path/'ledger.json'
    with pytest.raises(ValueError):
        record_observation(path,row)
    assert not path.exists()
