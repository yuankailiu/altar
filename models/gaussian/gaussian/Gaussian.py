# -*- python -*-
# -*- coding: utf-8 -*-
#
# michael a.g. aïvázis <michael.aivazis@para-sim.com>
#
# (c) 2013-2018 parasim inc
# (c) 2010-2018 california institute of technology
# all rights reserved
#


# externals
import math
# the package
import altar


# declaration
class Gaussian(altar.models.bayesian, family="altar.models.gaussian"):
    """
    A model that emulates the probability density for a single observation of the model
    parameters. The observation is treated as normally distributed around a given mean, with a
    covariance constructed out of its eigenvalues and a rotation in configuration
    space. Currently, only two dimensional parameter spaces are supported.
    """


    # user configurable state
    dof = altar.properties.int(default=2)
    dof.doc = "the number of variables"

    support = altar.properties.array(default=(-1,1))
    support.doc = "the support interval of the prior distribution"


    μ = altar.properties.array(default=(0,0))
    μ.doc = 'the location of the central value of the observation'

    λ = altar.properties.array(default=(.01, .005))
    λ.doc = 'the eigenvalues of the covariance matrix'

    φ = altar.properties.dimensional(default=0*altar.units.angle.rad)
    φ.doc = 'the orientation of the covariance semi-major axis'


    # protocol obligations
    @altar.export
    def parameters(self):
        """
        The number of parameters in this model
        """
        # return the number of degrees of freedom
        return self.dof


    @altar.export
    def initialize(self, application):
        """
        Initialize the state of the model given a {problem} specification
        """
        # chain up
        super().initialize(application=application)
        # get the random number generator from my controller
        rng = self.controller.rng
        # build my prior pdf
        self.priorPDF = altar.pdf.uniform(support=self.support, rng=rng.rng)
        # all done
        return self


    @altar.export
    def sample(self, step):
        """
        Fill {state.θ} with an initial random sample from my prior distribution.
        """
        # fill the sample set with random number from my prior
        step.theta.random(pdf=self.priorPDF)
        # and return
        return self


    @altar.export
    def priorLikelihood(self, step):
        """
        Fill {step.prior} with the likelihoods of the samples in {step.theta} in the prior
        distribution
        """
        # cache my pdf
        pdf = self.priorPDF
        # find out how many samples in the set
        samples = step.samples
        # grab the sample set
        θ = step.theta
        # and the storage for the prior likelihoods
        prior = state.prior
        # for each sample
        for sample in range(samples):
            # fill the vector with the log likelihoods in the prior
            prior[sample] = sum(math.log(pdf.density(parameter)) for parameter in θ.getRow(sample))
        # all done
        return self


    @altar.export
    def dataLikelihood(self, step):
        """
        Fill {state.data} with the likelihoods of the samples in {step.theta} given the available
        data. This is what is usually referred to as the "forward model"
        """
        # cache the inverse of {σ}
        σ_inv = self.σ_inv
        # find out how many samples in the set
        samples = step.samples

        # grab the sample set
        θ = step.theta
        # and the storage for the data likelihoods
        data = step.data

        # for each sample in the sample set
        for sample in range(samples):
            # prepare vector with the sample difference from the mean
            δ = θ.getRow(sample)
            δ -= self.peak
            # storage for {σ_inv . δ}
            y = altar.vector(shape=δ.shape).zero()
            # compute {σ_inv . δ} and store it in {y}
            altar.blas.dsymv(σ_inv.upperTriangular, 1.0, σ_inv, δ, 0.0, y)
            # finally, form {δ^T . σ_inv . δ}
            v = altar.blas.ddot(δ, y)
            # compute and return the log-likelihood of the data given this sample
            data[sample] = self.normalization - v/2

        # all done
        return self


    @altar.export
    def verify(self, step):
        """
        Check whether the samples in {step.θ} are consistent with the model requirements and
        return a vector with zeroes for valid samples and ones for the invalid ones
        """
        # unpack my support
        low, high = self.support
        # build the rejection map
        rejects = altar.vector(shape=step.samples).zero()

        # grab the sample set
        θ = step.theta
        # go through the samples in θ
        for sample in range(θ.rows):
            # and the parameters in this sample
            for parameter in range(θ.columns):
                # if the parameter lies outside my support
                if not (low <= θ[sample,parameter] <= high):
                    # the entire sample is invalid
                    # print(" *** INVALID PARAMETER ***")
                    rejects[sample] = 1
                    # so skip checking the rest of the parameters
                    break

        # all done; return the rejection map
        return rejects


    # meta methods
    def __init__(self, **kwds):
        # chain up
        super().__init__(**kwds)

        # the number of model parameters
        dof = self.dof

        # convert the central value into a vector; allocate
        peak = altar.vector(shape=dof)
        # and populate
        for index, value in enumerate(self.μ): peak[index] = value

        # the trigonometry
        cos_φ = math.cos(self.φ)
        sin_φ = math.sin(self.φ)
        # the eigenvalues
        λ0 = self.λ[0]
        λ1 = self.λ[1]
        # the eigenvalue inverses
        λ0_inv = 1/λ0
        λ1_inv = 1/λ1

        # build the inverse of the covariance matrix
        σ_inv = altar.matrix(shape=(dof, dof))
        σ_inv[0,0] = λ0_inv*cos_φ**2 +  λ1_inv*sin_φ**2
        σ_inv[1,1] = λ1_inv*cos_φ**2 +  λ0_inv*sin_φ**2
        σ_inv[0,1] = σ_inv[1,0] = (λ1_inv - λ0_inv) * cos_φ * sin_φ

        # compute its determinant and store it
        σ_lndet = math.log(λ0 * λ1)

        # local names for the math functions
        log, π = math.log, math.pi

        # attach the characteristics of my pdf
        self.peak = peak
        self.σ_inv = σ_inv

        # the log-normalization
        self.normalization = -.5*(dof*log(2*π) + σ_lndet)

        # all done
        return


    # implementation details
    peak = None # the location of my central value
    σ_inv = None # the inverse of my data covariance
    normalization = 1 # the normalization factor for my prior distribution

    priorPDF = None # my prior probability distribution function; set in {initialize}


# end of file