from . import loadDefaultParams as dp
from . import timeIntegration as ti
from ..model import Model


class WCModel(Model):
    """
    The two-population Wilson-Cowan model
    """

    name = "wc"
    description = "Wilson-Cowan model"

    # init_vars extended by the initial adaptation value: adap_init
    init_vars = ["exc_init", "inh_init", "adap_init", "exc_ou", "inh_ou"]
    #"adap" is added to the output- & state_vars, such that it is saved in the output-dict in self.storeOutputsAndStates in model class.
    state_vars = ["exc", "inh", "adap", "exc_ou", "inh_ou"]#, "r_e", "r_i"]
    output_vars = ["exc", "inh", "adap"]#, "r_e", "r_i"]
    default_output = "exc"
    input_vars = ["exc_ext", "inh_ext"]
    default_input = "exc_ext"

    # because this is not a rate model, the input
    # to the bold model must be transformed
    boldInputTransform = lambda self, x: x * 50

    def __init__(self, params=None, Cmat=None, Dmat=None, seed=None):

        self.Cmat = Cmat
        self.Dmat = Dmat
        self.seed = seed

        # the integration function must be passed
        integration = ti.timeIntegration

        # load default parameters if none were given
        if params is None:
            params = dp.loadDefaultParams(Cmat=self.Cmat, Dmat=self.Dmat, seed=self.seed)

        # Initialize base class Model
        super().__init__(integration=integration, params=params)
